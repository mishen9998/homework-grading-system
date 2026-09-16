from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app import db
from app.models import User, Organization
from app.services.organization_context import (
    audit, check_organization_policy, current_user,
    organization_is_expired, session_claims,
)
from werkzeug.security import check_password_hash
import os
import uuid
from werkzeug.utils import secure_filename
import secrets
import string

bp = Blueprint('auth', __name__, url_prefix='/api/auth')

ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_avatar_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS

def generate_friend_code(length=8):
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

@bp.route('/register', methods=['POST'])
def register():
    # Accounts and their authoritative school identifiers are provisioned by
    # an organization administrator; a public request cannot choose a tenant.
    return jsonify({'error': '注册已关闭，请联系机构管理员开通账号'}), 403

@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or any(
            not isinstance(data.get(key), str) or not data[key].strip()
            for key in ('organization_code', 'username', 'password')):
        return jsonify({'error': '请填写机构编码、账号和密码'}), 400
    if len(data['organization_code']) > 80 or len(data['username']) > 80 or len(data['password']) > 256:
        return jsonify({'error': '登录参数长度超限'}), 400
    if 'organization_id' in data:
        return jsonify({'error': '请使用机构编码登录'}), 400
    org = Organization.query.filter_by(code=data['organization_code'].strip().lower()).first()
    user = User.query.filter_by(organization_id=org.id, username=data['username'].strip()).first() if org else None
    if (not user or not check_password_hash(user.password, data['password']) or
            (data.get('role') is not None and data['role'] != user.role)):
        return jsonify({'error': '机构编码、账号或密码错误'}), 401
    check_organization_policy(user, org, allow_platform=True)
    access_token = create_access_token(identity=str(user.id), additional_claims=session_claims(user))
    return jsonify(message='登录成功', access_token=access_token, user=user.to_dict(),
                   organization=org.to_dict(), read_only=organization_is_expired(org)), 200

@bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user = current_user()
    org = db.session.get(Organization, user.organization_id)
    return jsonify(user=user.to_dict(), organization=org.to_dict(),
                   read_only=organization_is_expired(org)), 200


@bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    user = current_user()
    user.token_version += 1
    audit('session.logout', target_type='user', target_id=user.id)
    db.session.commit()
    return jsonify(message='已退出登录'), 200

@bp.route('/update-profile', methods=['PUT'])
@jwt_required()
def update_profile():
    user = current_user()
    data = request.get_json(silent=True)
    allowed = {'name': 100, 'email': 120, 'phone': 20, 'qq': 20}
    if not isinstance(data, dict):
        return jsonify(error='请求内容必须为对象'), 400
    if set(data) - set(allowed):
        return jsonify(error='身份、机构、学号、工号、班级等字段只能由机构管理员维护'), 403
    for key, value in data.items():
        if not isinstance(value, str) or len(value) > allowed[key] or (key in ('name', 'email') and not value.strip()):
            return jsonify(error=f'{key} 格式错误或长度超限'), 400
    if 'email' in data and User.query.filter(User.organization_id == user.organization_id,
            User.email == data['email'].strip(), User.id != user.id).first():
        return jsonify(error='邮箱已被使用'), 409
    for key, value in data.items():
        setattr(user, key, value.strip())
    try:
        audit('user.profile_updated', target_type='user', target_id=user.id,
              details={'fields': sorted(data)})
        db.session.commit()
        return jsonify({
            'message': '更新成功',
            'user': user.to_dict()
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({'error': '更新失败'}), 500

@bp.route('/upload-avatar', methods=['POST'])
@jwt_required()
def upload_avatar():
    logger = current_app.logger
    logger.info('收到上传头像请求')
    user_id = get_jwt_identity()

    user = User.query.get(user_id)

    if not user:
        return jsonify({'error': '用户不存在'}), 404

    if 'file' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400

    if not allowed_avatar_file(file.filename):
        logger.info(f'头像格式不支持: {file.filename}')
        return jsonify({'error': '只支持 png, jpg, jpeg, gif 格式的图片'}), 400

    filename = secure_filename(file.filename)
    unique_filename = f"avatar_{user_id}_{uuid.uuid4().hex}.{filename.rsplit('.', 1)[1].lower()}"

    upload_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tupian')
    os.makedirs(upload_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, unique_filename)
    file.save(file_path)

    avatar_url = f"/tupian/{unique_filename}"
    user.avatar_url = avatar_url

    try:
        db.session.commit()
        logger.info(f'头像上传成功 user_id={user_id}')
        return jsonify({
            'message': '头像上传成功',
            'avatar_url': avatar_url,
            'user': user.to_dict()
        }), 200
    except Exception:
        db.session.rollback()
        logger.exception(f'头像上传数据库更新失败 user_id={user_id}')
        return jsonify({'error': '头像上传失败'}), 500
