"""Platform customer metadata and organization-owned AI authorization."""
from datetime import datetime, timezone
import re

from flask import Blueprint, jsonify, request

from app import db
from app.models import Organization, User
from app.routes.admin import (
    clean_text, current_user_count, ensure_user_capacity, invalid, lock_organization, new_user,
    object_body, organization_users, pagination, transactional, user_values,
)
from app.services.organization_context import audit, current_organization, lock_current_identity
from app.utils import role_required

platform_bp = Blueprint('platform', __name__, url_prefix='/api/platform')
organization_bp = Blueprint('organization', __name__, url_prefix='/api/admin')
QUOTAS = {'user_limit', 'storage_limit_bytes', 'ai_monthly_token_limit', 'concurrent_task_limit'}
ORGANIZATION_FIELDS = {'name', 'status', 'expires_at'} | QUOTAS


def organization_values(data):
    values = {}
    if 'name' in data:
        values['name'] = clean_text(data['name'], 'name', 200, required=True)
    if 'status' in data:
        if data['status'] not in ('active', 'disabled'):
            invalid('status 仅允许 active 或 disabled')
        values['status'] = data['status']
    if 'expires_at' in data:
        value = data['expires_at']
        if value is None:
            values['expires_at'] = None
        else:
            if not isinstance(value, str):
                invalid('expires_at 必须为 ISO 8601 日期时间或 null')
            try:
                parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                if parsed.tzinfo is not None:
                    parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            except (ValueError, OverflowError):
                invalid('expires_at 日期时间格式无效')
            if parsed.year < 1000:
                invalid('expires_at 必须在 MySQL 支持的公元 1000–9999 年范围内')
            values['expires_at'] = parsed
    for field in QUOTAS:
        if field not in data:
            continue
        maximum = 2147483647 if field in ('user_limit', 'concurrent_task_limit') else 9223372036854775807
        if type(data[field]) is not int or not 0 <= data[field] <= maximum:
            invalid(f'{field} 必须为 0–{maximum} 范围内的整数')
        values[field] = data[field]
    return values


def customer(organization_id, *, lock=False):
    query = Organization.query.filter(Organization.id == organization_id, Organization.code != 'platform')
    if lock:
        query = query.populate_existing().with_for_update()
    organization = query.first()
    if organization is None:
        invalid('机构不存在', 404, 'not_found')
    return organization


def metadata(organization, count=None):
    result = organization.to_dict()
    result['user_count'] = organization_users(organization).count() if count is None else count
    return result


@platform_bp.get('/organizations')
@role_required('platform_admin')
def list_organizations():
    query = Organization.query.filter(Organization.code != 'platform')
    status = request.args.get('status')
    if status:
        if status not in ('active', 'disabled'):
            invalid('机构状态筛选无效')
        query = query.filter_by(status=status)
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(db.or_(Organization.name.contains(search), Organization.code.contains(search)))
    page = pagination(query.order_by(Organization.id.desc()))
    ids = [organization.id for organization in page.items]
    counts = dict(db.session.query(User.organization_id, db.func.count(User.id))
                  .filter(User.organization_id.in_(ids)).group_by(User.organization_id).all()) if ids else {}
    return jsonify({'organizations': [metadata(item, counts.get(item.id, 0)) for item in page.items],
                    'total': page.total, 'page': page.page, 'per_page': page.per_page, 'has_next': page.has_next})


@platform_bp.post('/organizations')
@role_required('platform_admin')
@transactional
def create_organization():
    lock_current_identity(roles=('platform_admin',), write=True, allow_platform=True)
    data = object_body(ORGANIZATION_FIELDS | {'code', 'admin'})
    code = clean_text(data.get('code'), 'code', 80, required=True).lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{1,79}', code) or code == 'platform':
        invalid('机构编码需为 2–80 位小写字母、数字、下划线或短横线，且不能为 platform')
    values = organization_values(data)
    if 'name' not in values:
        invalid('缺少机构名称')
    admin_data = data.get('admin')
    if not isinstance(admin_data, dict) or set(admin_data) - {'username', 'email', 'password', 'name'}:
        invalid('admin 必须包含 username、email、password、name，且不得指定角色或机构')
    if Organization.query.filter_by(code=code).first():
        invalid('机构编码已存在', 409, 'duplicate_organization')
    organization = Organization(code=code, ai_enabled=False, **values)
    db.session.add(organization)
    db.session.flush()
    ensure_user_capacity(organization)
    admin_values = user_values({**admin_data, 'role': 'admin', 'is_active': True}, organization)
    administrator = new_user(admin_values, organization)
    db.session.flush()
    audit('organization.created', organization_id=organization.id,
          target_type='organization', target_id=organization.id,
          details={'admin_id': administrator.id, 'ai_enabled': False})
    return jsonify({'organization': metadata(organization),
                    'admin': {'id': administrator.id, 'username': administrator.username, 'role': 'admin'}}), 201


@platform_bp.get('/organizations/<int:organization_id>')
@role_required('platform_admin')
def get_organization(organization_id):
    return jsonify({'organization': metadata(customer(organization_id))})


@platform_bp.put('/organizations/<int:organization_id>')
@role_required('platform_admin')
@transactional
def update_organization(organization_id):
    organization = customer(organization_id, lock=True)
    lock_current_identity(roles=('platform_admin',), write=True, allow_platform=True)
    data = object_body(ORGANIZATION_FIELDS)
    values = organization_values(data)
    if 'user_limit' in values and values['user_limit'] < current_user_count(organization):
        invalid('人员额度不能低于现有账号总数', 409, 'user_limit_below_usage')
    before = {key: organization.to_dict()[key] for key in values}
    for key, value in values.items():
        setattr(organization, key, value)
    db.session.flush()
    audit('organization.updated', organization_id=organization.id,
          target_type='organization', target_id=organization.id,
          details={'before': before, 'after': {key: organization.to_dict()[key] for key in values}})
    return jsonify({'organization': metadata(organization)})


@organization_bp.get('/organization')
@role_required('admin', 'teacher', 'student')
def get_own_organization():
    return jsonify({'organization': metadata(current_organization())})


@organization_bp.put('/organization')
@role_required('admin')
@transactional
def update_own_organization():
    organization = lock_organization()
    data = object_body({'ai_enabled'})
    if set(data) != {'ai_enabled'} or not isinstance(data['ai_enabled'], bool):
        invalid('仅接受布尔字段 ai_enabled')
    before = organization.ai_enabled
    organization.ai_enabled = data['ai_enabled']
    audit('organization.ai_authorization_changed', target_type='organization', target_id=organization.id,
          details={'before': before, 'after': organization.ai_enabled})
    return jsonify({'organization': metadata(organization)})
