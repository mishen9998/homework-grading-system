from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app import db
from app.models import User
from werkzeug.security import generate_password_hash, check_password_hash
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
    if not current_app.config.get('PUBLIC_REGISTRATION', True):
        return jsonify({'error': '注册已关闭，请联系管理员开通账号'}), 403
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password') or not data.get('role') or not data.get('name'):
        return jsonify({'error': '缺少必要字段'}), 400
    if data.get('role') == 'admin':
        return jsonify({'error': '管理员账号不能通过公开注册创建'}), 403
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': '该账号已被注册'}), 400
    
    email = data.get('email')
    if email and User.query.filter_by(email=email).first():
        return jsonify({'error': '邮箱已存在'}), 400
    
    if data['role'] not in ['student', 'teacher', 'admin']:
        return jsonify({'error': '角色必须是 student、teacher 或 admin'}), 400
    
    if data['role'] == 'student':
        if not data.get('student_id'):
            return jsonify({'error': '学生必须填写学号'}), 400
        if User.query.filter_by(student_id=data['student_id']).first():
            return jsonify({'error': '该学号已被注册'}), 400
    
    if data['role'] in ['teacher', 'admin']:
        teacher_id = data.get('teacher_id') or data.get('username')
        if User.query.filter_by(teacher_id=teacher_id).first():
            return jsonify({'error': '该工号已被注册'}), 400
    
    user = User(
        username=data['username'],
        password=generate_password_hash(data['password']),
        email=email or f"{data['username']}@example.com",
        role=data['role'],
        name=data['name'],
        college=data.get('college'),
        phone=data.get('phone'),
        qq=data.get('qq'),
        friend_code=generate_friend_code()
    )
    
    if data['role'] == 'student':
        user.student_id = data.get('student_id')
        user.class_name = data.get('class_name')
    
    if data['role'] in ['teacher', 'admin']:
        user.teacher_id = data.get('teacher_id') or data.get('username')
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'message': '注册成功',
        'user': user.to_dict()
    }), 201

@bp.route('/login', methods=['POST'])
def login():
    logger = current_app.logger
    logger.info('收到登录请求')

    try:
        data = request.get_json()

        if not data or not data.get('username') or not data.get('password'):
            return jsonify({'error': '缺少账号或密码'}), 400

        if not data.get('role'):
            return jsonify({'error': '请选择身份（学生或老师）'}), 400

        user = User.query.filter_by(username=data['username']).first()

        if not user:
            logger.info(f'登录失败：用户不存在 username={data.get("username")}')
            return jsonify({'error': '账号或密码错误'}), 401

        if not check_password_hash(user.password, data['password']):
            logger.info(f'登录失败：密码错误 username={data.get("username")}')
            return jsonify({'error': '账号或密码错误'}), 401

        if user.role != data.get('role'):
            logger.info(f'登录失败：身份不匹配 username={data.get("username")} role={user.role}')
            return jsonify({'error': f'身份不匹配，该账号是{"老师" if user.role == "teacher" else "学生"}账号'}), 401

        # 将 role 写入 JWT claims，后续接口可通过 @role_required 免查库鉴权
        access_token = create_access_token(
            identity=str(user.id),
            additional_claims={'role': user.role}
        )

        logger.info(f'登录成功 user_id={user.id} role={user.role}')

        return jsonify({
            'message': '登录成功',
            'access_token': access_token,
            'user': user.to_dict()
        }), 200
    except Exception:
        logger.exception('登录接口异常')
        return jsonify({'error': '登录失败，请稍后重试'}), 500

@bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    return jsonify({'user': user.to_dict()}), 200

@bp.route('/update-profile', methods=['PUT'])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    data = request.get_json()
    
    if data.get('name'):
        user.name = data['name']
    
    if 'student_id' in data:
        user.student_id = data['student_id']
    
    if 'teacher_id' in data:
        user.teacher_id = data['teacher_id']
    
    if 'phone' in data:
        user.phone = data['phone']
    
    if 'qq' in data:
        user.qq = data['qq']
    
    if 'class_name' in data:
        user.class_name = data['class_name']
    
    if 'college' in data:
        user.college = data['college']
    
    if data.get('email'):
        existing_user = User.query.filter(User.email == data['email'], User.id != user.id).first()
        if existing_user:
            return jsonify({'error': '邮箱已被使用'}), 400
        user.email = data['email']
    
    try:
        db.session.commit()
        return jsonify({
            'message': '更新成功',
            'user': user.to_dict()
        }), 200
    except Exception as e:
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

    upload_folder = current_app.config['UPLOAD_FOLDER']
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
