from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash
from app import db
from app.models import User
from app.utils import role_required
import openpyxl
from io import BytesIO

bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# 复用通用角色装饰器（基于 JWT claims 鉴权，免查库），兼容既有 @admin_required 用法
admin_required = role_required('admin')

@bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    role_filter = request.args.get('role')
    search = request.args.get('search', '')
    
    query = User.query
    
    if role_filter and role_filter in ['student', 'teacher']:
        query = query.filter_by(role=role_filter)
    
    if search:
        query = query.filter(
            db.or_(
                User.username.contains(search),
                User.name.contains(search),
                User.email.contains(search),
                User.student_id.contains(search)
            )
        )
    
    # 支持分页（传 page 参数启用），不传则全量返回以兼容旧前端
    page = request.args.get('page', type=int)
    if page:
        per_page = request.args.get('per_page', 20, type=int)
        paginated = query.order_by(User.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        return jsonify({
            'users': [u.to_dict() for u in paginated.items],
            'total': paginated.total,
            'page': page,
            'per_page': per_page,
            'has_next': paginated.has_next
        }), 200

    users = query.order_by(User.created_at.desc()).all()

    return jsonify({
        'users': [user.to_dict() for user in users],
        'total': len(users)
    }), 200

@bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user(user_id):
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    return jsonify({'user': user.to_dict()}), 200

@bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    data = request.get_json()
    
    if data.get('username') and data['username'] != user.username:
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': '账号已存在'}), 400
        user.username = data['username']
    
    if data.get('email') and data['email'] != user.email:
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': '邮箱已存在'}), 400
        user.email = data['email']
    
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
    
    if data.get('role') and data['role'] in ['student', 'teacher']:
        user.role = data['role']
    
    if data.get('password'):
        user.password = generate_password_hash(data['password'])
    
    try:
        db.session.commit()
        return jsonify({
            'message': '更新成功',
            'user': user.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': '更新失败'}), 500

@bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    if user.role == 'admin':
        return jsonify({'error': '不能删除管理员账号'}), 400
    
    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({'message': '删除成功'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': '删除失败'}), 500

@bp.route('/import', methods=['POST'])
@admin_required
def import_users():
    if 'file' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400
    
    file = request.files['file']
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'error': '只支持Excel文件（.xlsx或.xls）'}), 400
    
    try:
        wb = openpyxl.load_workbook(BytesIO(file.read()))
        ws = wb.active
        
        headers = [cell.value for cell in ws[1]]
        
        required_headers = ['账号', '密码', '邮箱', '角色', '姓名']
        for header in required_headers:
            if header not in headers:
                return jsonify({'error': f'Excel缺少必需列：{header}'}), 400
        
        success_count = 0
        error_list = []
        
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not any(row):
                continue
            
            row_data = dict(zip(headers, row))
            
            username = str(row_data.get('账号', '')).strip()
            password = str(row_data.get('密码', '')).strip()
            email = str(row_data.get('邮箱', '')).strip()
            role = str(row_data.get('角色', '')).strip().lower()
            name = str(row_data.get('姓名', '')).strip()
            
            if not all([username, password, email, role, name]):
                error_list.append(f'第{row_idx}行：缺少必要字段')
                continue
            
            if role not in ['student', 'teacher']:
                error_list.append(f'第{row_idx}行：角色必须是student或teacher')
                continue
            
            if User.query.filter_by(username=username).first():
                error_list.append(f'第{row_idx}行：账号 {username} 已存在')
                continue
            
            if User.query.filter_by(email=email).first():
                error_list.append(f'第{row_idx}行：邮箱 {email} 已存在')
                continue
            
            user = User(
                username=username,
                password=generate_password_hash(password),
                email=email,
                role=role,
                name=name,
                student_id=str(row_data.get('学号', '')).strip() if row_data.get('学号') else None,
                phone=str(row_data.get('电话', '')).strip() if row_data.get('电话') else None,
                qq=str(row_data.get('QQ', '')).strip() if row_data.get('QQ') else None,
                class_name=str(row_data.get('班级', '')).strip() if row_data.get('班级') else None,
                college=str(row_data.get('学院', '')).strip() if row_data.get('学院') else None
            )
            
            db.session.add(user)
            success_count += 1
        
        db.session.commit()
        
        return jsonify({
            'message': f'成功导入 {success_count} 个用户',
            'success_count': success_count,
            'error_count': len(error_list),
            'errors': error_list[:10]
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'导入失败：{str(e)}'}), 500

@bp.route('/template', methods=['GET'])
@admin_required
def download_template():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '用户导入模板'
    
    headers = ['账号', '密码', '邮箱', '角色', '姓名', '学号', '电话', 'QQ', '班级', '学院']
    ws.append(headers)
    
    example_data = [
        ['student001', '123456', 'student001@example.com', 'student', '张三', '2021001', '13800138000', '123456789', '计算机2101', '计算机学院'],
        ['teacher001', '123456', 'teacher001@example.com', 'teacher', '李老师', '', '13900139000', '987654321', '', '计算机学院']
    ]
    
    for data in example_data:
        ws.append(data)
    
    from io import BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    from flask import send_file
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='用户导入模板.xlsx'
    )

@bp.route('/statistics', methods=['GET'])
@admin_required
def get_statistics():
    total_users = User.query.count()
    student_count = User.query.filter_by(role='student').count()
    teacher_count = User.query.filter_by(role='teacher').count()
    admin_count = User.query.filter_by(role='admin').count()
    
    return jsonify({
        'total_users': total_users,
        'student_count': student_count,
        'teacher_count': teacher_count,
        'admin_count': admin_count
    }), 200
