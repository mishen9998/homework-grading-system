"""Database-backed identity and organization policy shared by HTTP and workers.

JWT claims bind a session to its original organization, role and token version.
They never grant authorization: every request reloads the current account and
organization. Workers must call ``check_organization_policy`` again at execution.
"""
from datetime import datetime

from flask import g, has_request_context, request
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request
from werkzeug.exceptions import HTTPException

from app import db


class PolicyError(HTTPException):
    def __init__(self, message, code=403, error_code='permission_denied'):
        super().__init__(description=message)
        self.code = code
        self.error_code = error_code


def current_user():
    user = getattr(g, 'current_user', None)
    if user is None:
        raise PolicyError('请重新登录', 401, 'authentication_required')
    return user


def current_organization():
    organization = getattr(g, 'organization', None)
    if organization is None:
        raise PolicyError('机构上下文无效', 401, 'invalid_organization_context')
    return organization


def organization_is_expired(organization):
    return bool(organization.expires_at and organization.expires_at <= datetime.utcnow())


def check_organization_policy(user, organization=None, *, write=False, external_ai=False,
                              allow_platform=False):
    """Enforce current DB state. Call with freshly loaded rows outside HTTP."""
    from app.models import Organization
    if user is None or not user.is_active:
        raise PolicyError('账号已停用或不存在', 401, 'account_inactive')
    if user.role not in ('student', 'teacher', 'admin', 'platform_admin'):
        raise PolicyError('账号身份无效', 403, 'invalid_role')
    organization = organization or db.session.get(Organization, user.organization_id)
    if organization is None or organization.id != user.organization_id:
        raise PolicyError('机构上下文无效', 401, 'invalid_organization_context')
    if (user.role == 'platform_admin') != (organization.code == 'platform'):
        raise PolicyError('平台身份与机构归属不匹配', 403, 'invalid_platform_identity')
    if organization.status != 'active':
        raise PolicyError('机构已停用，请联系平台管理员', 403, 'organization_disabled')
    if user.role == 'platform_admin' and not allow_platform:
        raise PolicyError('平台管理员无教学业务访问权限', 403, 'platform_business_denied')
    if (write or external_ai) and organization_is_expired(organization):
        raise PolicyError('机构已到期，仅可读取历史数据', 403, 'organization_expired')
    if external_ai and not organization.ai_enabled:
        raise PolicyError('机构尚未授权外部 AI', 403, 'ai_not_authorized')
    return organization


def require_organization_id():
    """Only a verified server context may supply an HTTP tenant default."""
    if not has_request_context():
        raise PolicyError('非请求操作必须显式指定 organization_id', 400,
                          'organization_required')
    return current_organization().id


def scoped_query(model):
    """Apply the current organization; never take an ID from a request body."""
    if current_user().role == 'platform_admin':
        raise PolicyError('平台管理员无教学业务访问权限', 403, 'platform_business_denied')
    return model.query.filter_by(organization_id=current_organization().id)


def audit(action, *, target_type=None, target_id=None, details=None, organization_id=None,
          actor=None):
    """Append to the caller's transaction; never commit partial business changes."""
    from app.models import AuditLog
    actor = actor or (getattr(g, 'current_user', None) if has_request_context() else None)
    row = AuditLog(organization_id=organization_id if organization_id is not None else
                   (actor.organization_id if actor else None),
                   actor_id=actor.id if actor else None, action=action,
                   target_type=target_type, target_id=str(target_id) if target_id is not None else None,
                   details=details or {})
    db.session.add(row)
    return row


def session_claims(user):
    return {'organization_id': user.organization_id, 'role': user.role,
            'token_version': user.token_version}


def _read_only_request():
    if request.endpoint == 'auth.logout':
        return True
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return True
    # Local retrieval uses POST for potentially long questions, without writes.
    if request.endpoint == 'knowledge.assistant':
        body = request.get_json(silent=True)
        return isinstance(body, dict) and body.get('mode', 'local') == 'local'
    return False


def _external_ai_request():
    # Admission policy remains useful before the persistent t3 gateway is
    # installed. That gateway repeats this check in the worker at execution.
    if request.endpoint == 'knowledge.assistant':
        body = request.get_json(silent=True)
        return isinstance(body, dict) and body.get('mode') == 'deepseek'
    return request.endpoint in {
        'ai_assistant.assistant', 'assignments.ai_grade_question',
        'assignments.generate_overall_comment', 'assignments.ai_grade_python_code',
        'assignments.test_ai_connection', 'assignments.ai_parse_questions',
    }


def authenticate_request():
    if request.method == 'OPTIONS' or not request.path.startswith('/api/'):
        return None
    if request.endpoint in ('auth.login', 'auth.register', 'health_check', 'readiness_check'):
        return None
    # Do not turn an unknown route into a misleading authentication error.
    if request.endpoint is None:
        return None
    verify_jwt_in_request()
    from app.models import Organization, User
    identity, claims = get_jwt_identity(), get_jwt()
    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        raise PolicyError('登录凭证无效，请重新登录', 401, 'stale_session')
    user = db.session.get(User, user_id)
    if user is None or not user.is_active:
        raise PolicyError('账号已停用或不存在', 401, 'account_inactive')
    if (claims.get('organization_id') != user.organization_id or
            claims.get('token_version') != user.token_version or claims.get('role') != user.role):
        raise PolicyError('登录凭证已失效，请重新登录', 401, 'stale_session')
    org = db.session.get(Organization, user.organization_id)
    platform_metadata = (request.blueprint == 'platform' or
                         request.endpoint in ('auth.get_current_user', 'auth.logout'))
    check_organization_policy(user, org, write=not _read_only_request(),
                              external_ai=_external_ai_request(),
                              allow_platform=platform_metadata)
    if request.blueprint == 'platform' and user.role != 'platform_admin':
        raise PolicyError('仅平台管理员可执行此操作')
    g.current_user, g.organization = user, org
    g.organization_id = org.id
    return None


def register_organization_context(app):
    app.before_request(authenticate_request)

    @app.errorhandler(PolicyError)
    def handle_policy_error(exc):
        return {'error': exc.description, 'code': exc.error_code}, exc.code
