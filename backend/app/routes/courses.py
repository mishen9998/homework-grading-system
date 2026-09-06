from flask import Blueprint, request, jsonify, send_from_directory, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import secrets
import os
import uuid
import random
import string
from werkzeug.utils import secure_filename
from app import db
from app.models import User, Course, CourseEnrollment, CourseResource, CourseNote, Assignment, Submission, Question, Message

bp = Blueprint('courses', __name__, url_prefix='/api/courses')

ALLOWED_EXTENSIONS = {
    'image': {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg'},
    'document': {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt'},
    'video': {'mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm'},
    'audio': {'mp3', 'wav', 'ogg', 'flac', 'aac'}
}

def allowed_file(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    for category in ALLOWED_EXTENSIONS:
        if ext in ALLOWED_EXTENSIONS[category]:
            return True, category
    return False, None

def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    for category, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return category
    return 'other'

def generate_course_code():
    chars = string.ascii_uppercase + string.digits
    code = ''.join(random.choice(chars) for _ in range(6))
    return code

@bp.route('/create', methods=['POST'])
@jwt_required()
def create_course():
    current_app.logger.info("收到创建课程请求")
    try:
        user_id = int(get_jwt_identity())
        current_app.logger.info(f"用户ID: {user_id}")
        user = User.query.get(user_id)
        current_app.logger.info(f"用户: {user}, 角色: {user.role if user else 'None'}")
        
        if not user or user.role != 'teacher':
            return jsonify({'error': '只有老师可以创建课程'}), 403
        
        data = request.get_json()
        current_app.logger.info(f"请求数据: {data}")
        
        if not data or not data.get('name'):
            return jsonify({'error': '缺少课程名称'}), 400
        
        code = generate_course_code()
        
        while Course.query.filter_by(code=code).first():
            code = generate_course_code()
        
        code_expiry = None
        if data.get('code_expiry'):
            try:
                code_expiry = datetime.fromisoformat(data['code_expiry'].replace('Z', '+00:00'))
            except:
                return jsonify({'error': '日期格式错误'}), 400
        
        course = Course(
            name=data['name'],
            code=code,
            code_expiry=code_expiry,
            teacher_id=user_id,
            description=data.get('description', ''),
            class_name=data.get('class_name', ''),
            expected_students=data.get('expected_students')
        )
        
        db.session.add(course)
        db.session.commit()
        
        current_app.logger.info(f"课程创建成功: {course.name}")
        
        return jsonify({
            'message': '课程创建成功',
            'course': course.to_dict()
        }), 201
    except Exception as e:
        current_app.logger.exception(f"创建课程出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@bp.route('/join', methods=['POST'])
@jwt_required()
def join_course():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'student':
        return jsonify({'error': '只有学生可以加入课程'}), 403
    
    data = request.get_json()
    
    if not data or not data.get('code'):
        return jsonify({'error': '缺少课程码'}), 400
    
    course = Course.query.filter_by(code=data['code'].upper()).first()
    
    if not course:
        return jsonify({'error': '课程码无效'}), 404
    
    if course.code_expiry and course.code_expiry < datetime.utcnow():
        return jsonify({'error': '课程码已过期'}), 400
    
    existing_enrollment = CourseEnrollment.query.filter_by(
        course_id=course.id,
        student_id=user_id
    ).first()
    
    if existing_enrollment:
        return jsonify({'error': '已经加入过此课程'}), 400
    
    enrollment = CourseEnrollment(
        course_id=course.id,
        student_id=user_id
    )
    
    db.session.add(enrollment)
    db.session.commit()
    
    return jsonify({
        'message': '加入课程成功',
        'enrollment': enrollment.to_dict()
    }), 201

@bp.route('/my-courses', methods=['GET'])
@jwt_required()
def get_my_courses():
    current_app.logger.info("收到获取课程列表请求")
    try:
        user_id = int(get_jwt_identity())
        current_app.logger.info(f"用户ID: {user_id}")
        user = User.query.get(user_id)
        current_app.logger.info(f"用户: {user}, 角色: {user.role if user else 'None'}")
        
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        if user.role == 'teacher':
            current_app.logger.info("老师查询课程")
            courses = Course.query.filter_by(teacher_id=user_id).all()
            courses_data = []
            for course in courses:
                course_dict = course.to_dict()
                course_dict['completed_assignments'] = 0
                course_dict['average_score'] = None
                courses_data.append(course_dict)
        else:
            current_app.logger.info("学生查询课程")
            enrollments = CourseEnrollment.query.filter_by(student_id=user_id).all()
            courses = [enrollment.course for enrollment in enrollments]
            courses_data = []
            for course in courses:
                course_dict = course.to_dict()
                courses_data.append(course_dict)
        
        current_app.logger.info(f"返回课程数量: {len(courses_data)}")
        return jsonify({
            'courses': courses_data
        }), 200
    except Exception as e:
        current_app.logger.exception(f"获取课程列表出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:course_id>', methods=['GET'])
@jwt_required()
def get_course_detail(course_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    course = Course.query.get(course_id)
    
    if not course:
        return jsonify({'error': '课程不存在'}), 404
    
    if user.role == 'student':
        enrollment = CourseEnrollment.query.filter_by(
            course_id=course_id,
            student_id=user_id
        ).first()
        
        if not enrollment:
            return jsonify({'error': '未加入此课程'}), 403
    
    return jsonify({
        'course': course.to_dict()
    }), 200

@bp.route('/<int:course_id>/students', methods=['GET'])
@jwt_required()
def get_course_students(course_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'teacher':
        return jsonify({'error': '只有老师可以查看学生列表'}), 403
    
    course = Course.query.get(course_id)
    
    if not course:
        return jsonify({'error': '课程不存在'}), 404
    
    if course.teacher_id != user_id:
        return jsonify({'error': '无权查看此课程'}), 403
    
    enrollments = CourseEnrollment.query.filter_by(course_id=course_id).all()
    students = []
    for enrollment in enrollments:
        if enrollment.student:
            students.append({
                'id': enrollment.student.id,
                'name': enrollment.student.name,
                'class_name': enrollment.student.class_name,
                'joined_at': enrollment.joined_at.isoformat() if enrollment.joined_at else None
            })
    
    return jsonify({
        'students': students
        }), 200

@bp.route('/<int:course_id>/assignments', methods=['GET'])
@jwt_required()
def get_course_assignments(course_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    course = Course.query.get(course_id)
    
    if not course:
        return jsonify({'error': '课程不存在'}), 404
    
    if user.role == 'student':
        enrollment = CourseEnrollment.query.filter_by(
            course_id=course_id,
            student_id=user_id
        ).first()
        
        if not enrollment:
            return jsonify({'error': '未加入此课程'}), 403
    
    assignments = Assignment.query.filter_by(course_id=course_id).all()
    
    assignments_data = []
    for assignment in assignments:
        assignment_dict = assignment.to_dict()
        assignment_dict['question_count'] = Question.query.filter_by(assignment_id=assignment.id).count()
        assignment_dict['submission_count'] = Submission.query.filter_by(assignment_id=assignment.id).count()
        assignment_dict['pending_count'] = Submission.query.filter_by(
            assignment_id=assignment.id,
            status='submitted'
        ).count()
        assignments_data.append(assignment_dict)
    
    return jsonify({
        'assignments': assignments_data
    }), 200

@bp.route('/<int:course_id>/assignments', methods=['POST'])
@jwt_required()
def create_course_assignment(course_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'teacher':
        return jsonify({'error': '只有老师可以创建作业'}), 403
    
    course = Course.query.get(course_id)
    
    if not course:
        return jsonify({'error': '课程不存在'}), 404
    
    if course.teacher_id != user_id:
        return jsonify({'error': '无权操作此课程'}), 403
    
    data = request.get_json()
    
    if not data or not data.get('title') or not data.get('due_date'):
        return jsonify({'error': '缺少必要字段（标题和截止时间）'}), 400
    
    try:
        due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
    except:
        return jsonify({'error': '日期格式错误'}), 400
    
    assignment = Assignment(
        title=data['title'],
        description=data.get('description', ''),
        due_date=due_date,
        teacher_id=user_id,
        course_id=course_id
    )
    
    db.session.add(assignment)
    db.session.commit()
    
    return jsonify({
        'message': '作业创建成功',
        'assignment': assignment.to_dict()
    }), 201

@bp.route('/<int:course_id>/resources', methods=['GET'])
@jwt_required()
def get_course_resources(course_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    course = Course.query.get(course_id)
    
    if not course:
        return jsonify({'error': '课程不存在'}), 404
    
    if user.role == 'student':
        enrollment = CourseEnrollment.query.filter_by(
            course_id=course_id,
            student_id=user_id
        ).first()
        
        if not enrollment:
            return jsonify({'error': '未加入此课程'}), 403
    
    resources = CourseResource.query.filter_by(course_id=course_id).all()
    
    return jsonify({
        'resources': [resource.to_dict() for resource in resources]
    }), 200

@bp.route('/<int:course_id>/resources', methods=['POST'])
@jwt_required()
def create_resource(course_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'teacher':
        return jsonify({'error': '只有老师可以创建资源'}), 403
    
    course = Course.query.get(course_id)
    
    if not course:
        return jsonify({'error': '课程不存在'}), 404
    
    if course.teacher_id != user_id:
        return jsonify({'error': '无权操作此课程'}), 403
    
    if 'file' in request.files:
        file = request.files['file']
        title = request.form.get('title', '')
        description = request.form.get('description', '')
        
        if not file or file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        is_allowed, file_category = allowed_file(file.filename)
        if not is_allowed:
            return jsonify({'error': '不支持的文件类型'}), 400
        
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        
        upload_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tupian')
        os.makedirs(upload_folder, exist_ok=True)
        
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        file_size = os.path.getsize(file_path)
        file_url = f"/tupian/{unique_filename}"
        
        if not title:
            title = filename
        
        resource = CourseResource(
            course_id=course_id,
            title=title,
            description=description,
            url=file_url,
            file_type=file_category,
            file_size=file_size,
            file_name=filename
        )
    else:
        data = request.get_json()
        
        if not data or not data.get('title') or not data.get('url'):
            return jsonify({'error': '缺少必要字段'}), 400
        
        resource = CourseResource(
            course_id=course_id,
            title=data['title'],
            description=data.get('description', ''),
            url=data['url'],
            file_type=data.get('file_type', 'link'),
            file_size=data.get('file_size'),
            file_name=data.get('file_name')
        )
    
    db.session.add(resource)
    db.session.commit()
    
    return jsonify({
        'message': '资源创建成功',
        'resource': resource.to_dict()
    }), 201

@bp.route('/upload-resource', methods=['POST'])
@jwt_required()
def upload_resource_file():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'teacher':
        return jsonify({'error': '只有老师可以上传资源'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    is_allowed, file_category = allowed_file(file.filename)
    if not is_allowed:
        return jsonify({'error': '不支持的文件类型'}), 400
    
    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    
    upload_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tupian')
    os.makedirs(upload_folder, exist_ok=True)
    
    file_path = os.path.join(upload_folder, unique_filename)
    file.save(file_path)
    
    file_size = os.path.getsize(file_path)
    file_url = f"/tupian/{unique_filename}"
    
    return jsonify({
        'message': '上传成功',
        'url': file_url,
        'file_type': file_category,
        'file_size': file_size,
        'file_name': filename
    }), 200

@bp.route('/resources/<int:resource_id>', methods=['DELETE'])
@jwt_required()
def delete_resource(resource_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'teacher':
        return jsonify({'error': '只有老师可以删除资源'}), 403
    
    resource = CourseResource.query.get(resource_id)
    
    if not resource:
        return jsonify({'error': '资源不存在'}), 404
    
    course = Course.query.get(resource.course_id)
    if course.teacher_id != user_id:
        return jsonify({'error': '无权删除此资源'}), 403
    
    if resource.url and resource.url.startswith('/tupian/'):
        try:
            file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tupian', resource.url.replace('/tupian/', ''))
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"删除文件失败: {e}")
    
    db.session.delete(resource)
    db.session.commit()
    
    return jsonify({'message': '资源删除成功'}), 200

@bp.route('/<int:course_id>/notes', methods=['GET'])
@jwt_required()
def get_course_notes(course_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'student':
        return jsonify({'error': '只有学生可以查看笔记'}), 403
    
    course = Course.query.get(course_id)
    
    if not course:
        return jsonify({'error': '课程不存在'}), 404
    
    enrollment = CourseEnrollment.query.filter_by(
        course_id=course_id,
        student_id=user_id
    ).first()
    
    if not enrollment:
        return jsonify({'error': '未加入此课程'}), 403
    
    notes = CourseNote.query.filter_by(
        course_id=course_id,
        student_id=user_id
    ).all()
    
    return jsonify({
        'notes': [note.to_dict() for note in notes]
    }), 200

@bp.route('/<int:course_id>/notes', methods=['POST'])
@jwt_required()
def create_note(course_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'student':
        return jsonify({'error': '只有学生可以创建笔记'}), 403
    
    course = Course.query.get(course_id)
    
    if not course:
        return jsonify({'error': '课程不存在'}), 404
    
    enrollment = CourseEnrollment.query.filter_by(
        course_id=course_id,
        student_id=user_id
    ).first()
    
    if not enrollment:
        return jsonify({'error': '未加入此课程'}), 403
    
    data = request.get_json()
    
    if not data or not data.get('title') or not data.get('content'):
        return jsonify({'error': '缺少必要字段'}), 400
    
    note = CourseNote(
        course_id=course_id,
        student_id=user_id,
        title=data['title'],
        content=data['content']
    )
    
    db.session.add(note)
    db.session.commit()
    
    return jsonify({
        'message': '笔记创建成功',
        'note': note.to_dict()
    }), 201

@bp.route('/notes/<int:note_id>', methods=['PUT'])
@jwt_required()
def update_note(note_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'student':
        return jsonify({'error': '只有学生可以编辑笔记'}), 403
    
    note = CourseNote.query.get(note_id)
    
    if not note:
        return jsonify({'error': '笔记不存在'}), 404
    
    if note.student_id != user_id:
        return jsonify({'error': '无权编辑此笔记'}), 403
    
    data = request.get_json()
    
    if data.get('title'):
        note.title = data['title']
    if data.get('content'):
        note.content = data['content']
    
    note.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'message': '笔记更新成功',
        'note': note.to_dict()
    }), 200

@bp.route('/notes/<int:note_id>', methods=['DELETE'])
@jwt_required()
def delete_note(note_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'student':
        return jsonify({'error': '只有学生可以删除笔记'}), 403
    
    note = CourseNote.query.get(note_id)
    
    if not note:
        return jsonify({'error': '笔记不存在'}), 404
    
    if note.student_id != user_id:
        return jsonify({'error': '无权删除此笔记'}), 403
    
    db.session.delete(note)
    db.session.commit()
    
    return jsonify({
        'message': '笔记删除成功'
    }), 200

@bp.route('/pending-assignments', methods=['GET'])
@jwt_required()
def get_pending_assignments():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'student':
        return jsonify({'error': '只有学生可以查看未完成作业'}), 403
    
    enrollments = CourseEnrollment.query.filter_by(student_id=user_id).all()
    course_ids = [e.course_id for e in enrollments]
    
    submitted_assignment_ids = db.session.query(Submission.assignment_id).filter(
        Submission.student_id == user_id
    ).all()
    submitted_ids = [aid[0] for aid in submitted_assignment_ids]
    
    now = datetime.utcnow()
    
    query = Assignment.query.filter(
        Assignment.course_id.in_(course_ids),
        ~Assignment.id.in_(submitted_ids)
    )
    
    pending_assignments = query.order_by(Assignment.due_date.asc()).all()
    
    assignments_data = []
    for assignment in pending_assignments:
        course = Course.query.get(assignment.course_id)
        is_overdue = assignment.due_date < now
        
        assignments_data.append({
            'id': assignment.id,
            'title': assignment.title,
            'course_name': course.name if course else '未知课程',
            'course_id': assignment.course_id,
            'due_date': assignment.due_date.isoformat(),
            'is_overdue': is_overdue,
            'days_remaining': (assignment.due_date - now).days if not is_overdue else 0
        })
    
    return jsonify({
        'pending_assignments': assignments_data,
        'total': len(assignments_data)
    }), 200

@bp.route('/<int:course_id>/reset-code', methods=['POST'])
@jwt_required()
def reset_course_code(course_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'teacher':
        return jsonify({'error': '只有老师可以重置课程码'}), 403
    
    course = Course.query.get(course_id)
    
    if not course:
        return jsonify({'error': '课程不存在'}), 404
    
    if course.teacher_id != user_id:
        return jsonify({'error': '无权操作此课程'}), 403
    
    code = generate_course_code()
    
    while Course.query.filter_by(code=code).first():
        code = generate_course_code()
    
    course.code = code
    
    try:
        db.session.commit()
        return jsonify({
            'message': '课程码重置成功',
            'code': code,
            'course': course.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': '重置失败'}), 500

@bp.route('/teacher/pending-submissions', methods=['GET'])
@jwt_required()
def get_teacher_pending_submissions():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'teacher':
        return jsonify({'error': '只有老师可以查看待批改作业'}), 403
    
    courses = Course.query.filter_by(teacher_id=user_id).all()
    course_ids = [c.id for c in courses]
    
    assignments = Assignment.query.filter(Assignment.course_id.in_(course_ids)).all()
    
    pending_count = 0
    pending_assignments = []
    
    for assignment in assignments:
        pending_submissions = Submission.query.filter_by(
            assignment_id=assignment.id,
            status='submitted'
        ).all()
        
        if pending_submissions:
            course = Course.query.get(assignment.course_id)
            pending_assignments.append({
                'assignment_id': assignment.id,
                'assignment_title': assignment.title,
                'course_id': assignment.course_id,
                'course_name': course.name if course else '未知课程',
                'pending_count': len(pending_submissions),
                'due_date': assignment.due_date.isoformat() if assignment.due_date else None
            })
            pending_count += len(pending_submissions)
    
    return jsonify({
        'total_pending': pending_count,
        'pending_assignments': pending_assignments
    }), 200

@bp.route('/assignments/<int:assignment_id>/unsubmitted-students', methods=['GET'])
@jwt_required()
def get_unsubmitted_students(assignment_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'teacher':
        return jsonify({'error': '只有老师可以查看未提交学生'}), 403
    
    assignment = Assignment.query.get(assignment_id)
    
    if not assignment:
        return jsonify({'error': '作业不存在'}), 404
    
    course = Course.query.get(assignment.course_id)
    
    if not course or course.teacher_id != user_id:
        return jsonify({'error': '无权操作此作业'}), 403
    
    enrollments = CourseEnrollment.query.filter_by(course_id=assignment.course_id).all()
    enrolled_student_ids = [e.student_id for e in enrollments]
    
    submitted_student_ids = db.session.query(Submission.student_id).filter(
        Submission.assignment_id == assignment_id
    ).all()
    submitted_ids = [sid[0] for sid in submitted_student_ids]
    
    unsubmitted_ids = [sid for sid in enrolled_student_ids if sid not in submitted_ids]
    
    unsubmitted_students = User.query.filter(User.id.in_(unsubmitted_ids)).all()
    
    students_data = []
    for student in unsubmitted_students:
        students_data.append({
            'id': student.id,
            'name': student.name,
            'student_id': student.student_id,
            'class_name': student.class_name
        })
    
    return jsonify({
        'assignment_id': assignment_id,
        'assignment_title': assignment.title,
        'total_enrolled': len(enrolled_student_ids),
        'submitted_count': len(submitted_ids),
        'unsubmitted_count': len(unsubmitted_students),
        'unsubmitted_students': students_data
    }), 200

@bp.route('/assignments/<int:assignment_id>/send-reminder', methods=['POST'])
@jwt_required()
def send_assignment_reminder(assignment_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'teacher':
        return jsonify({'error': '只有老师可以发送提醒'}), 403
    
    assignment = Assignment.query.get(assignment_id)
    
    if not assignment:
        return jsonify({'error': '作业不存在'}), 404
    
    course = Course.query.get(assignment.course_id)
    
    if not course or course.teacher_id != user_id:
        return jsonify({'error': '无权操作此作业'}), 403
    
    data = request.get_json() or {}
    student_ids = data.get('student_ids', [])
    custom_message = data.get('message', '')
    
    if not student_ids:
        enrollments = CourseEnrollment.query.filter_by(course_id=assignment.course_id).all()
        enrolled_student_ids = [e.student_id for e in enrollments]
        
        submitted_student_ids = db.session.query(Submission.student_id).filter(
            Submission.assignment_id == assignment_id
        ).all()
        submitted_ids = [sid[0] for sid in submitted_student_ids]
        
        student_ids = [sid for sid in enrolled_student_ids if sid not in submitted_ids]
    
    title = f'作业提醒：{assignment.title}'
    content = custom_message if custom_message else f'您有一份作业《{assignment.title}》尚未提交，请尽快完成。截止时间：{assignment.due_date.strftime("%Y-%m-%d %H:%M") if assignment.due_date else "未设置"}'
    
    sent_count = 0
    for student_id in student_ids:
        student = User.query.get(student_id)
        if student and student.role == 'student':
            message = Message(
                sender_id=user_id,
                receiver_id=student_id,
                title=title,
                content=content,
                message_type='assignment_reminder',
                related_assignment_id=assignment_id,
                related_course_id=assignment.course_id
            )
            db.session.add(message)
            sent_count += 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'已向 {sent_count} 名学生发送提醒',
        'sent_count': sent_count
    }), 200

@bp.route('/messages', methods=['GET'])
@jwt_required()
def get_messages():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    messages = Message.query.filter_by(receiver_id=user_id).order_by(Message.created_at.desc()).all()
    
    return jsonify({
        'messages': [m.to_dict() for m in messages],
        'unread_count': len([m for m in messages if not m.is_read])
    }), 200

@bp.route('/messages/<int:message_id>/read', methods=['PUT'])
@jwt_required()
def mark_message_read(message_id):
    user_id = int(get_jwt_identity())
    
    message = Message.query.get(message_id)
    
    if not message:
        return jsonify({'error': '消息不存在'}), 404
    
    if message.receiver_id != user_id:
        return jsonify({'error': '无权操作此消息'}), 403
    
    message.is_read = True
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '已标记为已读'
    }), 200

@bp.route('/assignments/<int:assignment_id>/statistics', methods=['GET'])
@jwt_required()
def get_assignment_statistics(assignment_id):
    try:
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        
        if not user or user.role != 'teacher':
            return jsonify({'error': '只有老师可以查看统计'}), 403
        
        assignment = Assignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'error': '作业不存在'}), 404
        
        course = Course.query.get(assignment.course_id)
        if not course or course.teacher_id != user_id:
            return jsonify({'error': '无权查看此作业'}), 403
        
        from app.models import Answer
        
        enrollments = CourseEnrollment.query.filter_by(course_id=assignment.course_id).all()
        enrolled_student_ids = [e.student_id for e in enrollments]
        total_students = len(enrolled_student_ids)
        
        submissions = Submission.query.filter_by(assignment_id=assignment_id).all()
        submitted_count = len(submissions)
        
        submitted_students = []
        unsubmitted_students = []
        score_ranking = []
        
        submitted_student_ids = set()
        for submission in submissions:
            student = User.query.get(submission.student_id)
            if student:
                submitted_student_ids.add(submission.student_id)
                student_info = {
                    'id': student.id,
                    'name': student.name if student.name else '',
                    'student_id': student.student_id if student.student_id else '',
                    'score': submission.score if submission.score else 0,
                    'status': submission.status if submission.status else ''
                }
                submitted_students.append(student_info)
                
                if submission.status == 'graded' and submission.score is not None:
                    score_ranking.append({
                        'id': student.id,
                        'name': student.name if student.name else '',
                        'student_id': student.student_id if student.student_id else '',
                        'score': submission.score,
                        'score_display': submission.score,
                        'status': 'graded'
                    })
                elif submission.status == 'submitted':
                    score_ranking.append({
                        'id': student.id,
                        'name': student.name if student.name else '',
                        'student_id': student.student_id if student.student_id else '',
                        'score': -1,
                        'score_display': '待批改',
                        'status': 'submitted'
                    })
        
        for student_id in enrolled_student_ids:
            if student_id not in submitted_student_ids:
                student = User.query.get(student_id)
                if student:
                    unsubmitted_students.append({
                        'id': student.id,
                        'name': student.name if student.name else '',
                        'student_id': student.student_id if student.student_id else ''
                    })
                    score_ranking.append({
                        'id': student.id,
                        'name': student.name if student.name else '',
                        'student_id': student.student_id if student.student_id else '',
                        'score': -2,
                        'score_display': '未提交',
                        'status': 'unsubmitted'
                    })
        
        score_ranking.sort(key=lambda x: x['score'], reverse=True)
        
        graded_submissions = [s for s in submissions if s.status == 'graded']
        graded_count = len(graded_submissions)
        
        pending_count = len([s for s in submissions if s.status == 'submitted'])
        
        scores = []
        score_distribution = {'excellent': 0, 'good': 0, 'medium': 0, 'pass': 0, 'fail': 0}
        
        total_score = assignment.total_score if assignment.total_score else 100
        
        for submission in graded_submissions:
            if submission.score is not None:
                score = submission.score
                scores.append(score)
                percentage = (score / total_score * 100) if total_score > 0 else 0
                
                if percentage >= 90:
                    score_distribution['excellent'] += 1
                elif percentage >= 80:
                    score_distribution['good'] += 1
                elif percentage >= 70:
                    score_distribution['medium'] += 1
                elif percentage >= 60:
                    score_distribution['pass'] += 1
                else:
                    score_distribution['fail'] += 1
        
        avg_score = sum(scores) / len(scores) if scores else 0
        max_score = max(scores) if scores else 0
        min_score = min(scores) if scores else 0
        
        questions = Question.query.filter_by(assignment_id=assignment_id).order_by(Question.question_number).all()
        question_stats = []
        
        for question in questions:
            answers = Answer.query.filter_by(question_id=question.id).all()
            graded_answers = [a for a in answers if a.is_correct is not None or a.score is not None]
            
            correct_count = len([a for a in graded_answers if a.is_correct == True])
            total_graded = len(graded_answers)
            
            option_stats = None
            if question.question_type == 'choice' and question.options:
                import json
                try:
                    options = json.loads(question.options) if isinstance(question.options, str) else question.options
                    option_stats = {}
                    for key in options.keys():
                        option_stats[key] = len([a for a in answers if a.answer_text == key])
                except:
                    option_stats = None
            
            content = question.content if question.content else ''
            content_preview = content[:50] + '...' if len(content) > 50 else content
            
            question_stats.append({
                'question_number': question.question_number,
                'question_type': question.question_type if question.question_type else 'text',
                'content': content_preview,
                'score': question.score if question.score else 0,
                'correct_count': correct_count,
                'total_graded': total_graded,
                'correct_rate': round(correct_count / total_graded * 100, 1) if total_graded > 0 else 0,
                'option_stats': option_stats
            })
        
        return jsonify({
            'assignment': {
                'id': assignment.id,
                'title': assignment.title if assignment.title else '',
                'total_score': total_score,
                'due_date': assignment.due_date.isoformat() if assignment.due_date else None
            },
            'summary': {
                'total_students': total_students,
                'submitted_count': submitted_count,
                'unsubmitted_count': len(unsubmitted_students),
                'graded_count': graded_count,
                'pending_count': pending_count,
                'submission_rate': round(submitted_count / total_students * 100, 1) if total_students > 0 else 0
            },
            'score_stats': {
                'avg_score': round(avg_score, 1),
                'max_score': max_score,
                'min_score': min_score,
                'distribution': score_distribution
            },
            'submitted_students': submitted_students,
            'unsubmitted_students': unsubmitted_students,
            'score_ranking': score_ranking,
            'question_stats': question_stats
        }), 200
    except Exception as e:
        import traceback
        print(f"统计API错误: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500
