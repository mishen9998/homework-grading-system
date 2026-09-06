from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename
from app import db
from app.models import User, Assignment, Question, Answer, Submission

bp = Blueprint('questions', __name__, url_prefix='/api/questions')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/upload-image', methods=['POST'])
@jwt_required()
def upload_question_image():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'teacher':
        return jsonify({'error': '只有老师可以上传图片'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        
        upload_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tupian')
        os.makedirs(upload_folder, exist_ok=True)
        
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        return jsonify({
            'message': '上传成功',
            'image_url': f"/tupian/{unique_filename}"
        }), 200
    
    return jsonify({'error': '不支持的文件类型'}), 400

@bp.route('/assignment/<int:assignment_id>', methods=['GET'])
@jwt_required()
def get_questions(assignment_id):
    assignment = Assignment.query.get(assignment_id)
    
    if not assignment:
        return jsonify({'error': '作业不存在'}), 404
    
    questions = Question.query.filter_by(assignment_id=assignment_id).order_by(Question.question_number).all()
    
    return jsonify({
        'questions': [q.to_dict() for q in questions]
    }), 200

@bp.route('', methods=['POST'])
@jwt_required()
def create_question():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'teacher':
        return jsonify({'error': '只有老师可以创建题目'}), 403
    
    data = request.get_json()
    
    if not data or not data.get('assignment_id') or not data.get('content'):
        return jsonify({'error': '缺少必要字段'}), 400
    
    assignment = Assignment.query.get(data['assignment_id'])
    if not assignment:
        return jsonify({'error': '作业不存在'}), 404
    
    if assignment.teacher_id != user_id:
        return jsonify({'error': '无权操作此作业'}), 403
    
    existing_count = Question.query.filter_by(assignment_id=data['assignment_id']).count()
    question_number = data.get('question_number', existing_count + 1)
    
    question = Question(
        assignment_id=data['assignment_id'],
        question_number=question_number,
        question_type=data.get('question_type', 'text'),
        content=data['content'],
        image_url=data.get('image_url'),
        correct_answer=data.get('correct_answer'),
        score=data.get('score', 10)
    )
    
    if data.get('options'):
        question.set_options(data['options'])
    
    db.session.add(question)
    db.session.commit()
    
    return jsonify({
        'message': '题目创建成功',
        'question': question.to_dict()
    }), 201

@bp.route('/batch', methods=['POST'])
@jwt_required()
def create_questions_batch():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'teacher':
        return jsonify({'error': '只有老师可以创建题目'}), 403
    
    data = request.get_json()
    
    if not data or not data.get('assignment_id'):
        return jsonify({'error': '缺少必要字段'}), 400
    
    assignment = Assignment.query.get(data['assignment_id'])
    if not assignment:
        return jsonify({'error': '作业不存在'}), 404
    
    if assignment.teacher_id != user_id:
        return jsonify({'error': '无权操作此作业'}), 403
    
    Question.query.filter_by(assignment_id=data['assignment_id']).delete()
    
    created_questions = []
    total_score = 0
    
    questions_data = data.get('questions', [])
    for idx, q_data in enumerate(questions_data, 1):
        question = Question(
            assignment_id=data['assignment_id'],
            question_number=idx,
            question_type=q_data.get('question_type', 'text'),
            content=q_data.get('content', ''),
            image_url=q_data.get('image_url'),
            correct_answer=q_data.get('correct_answer'),
            score=q_data.get('score', 10)
        )
        
        if q_data.get('options'):
            question.set_options(q_data['options'])
        
        db.session.add(question)
        created_questions.append(question)
        total_score += question.score
    
    assignment.total_score = total_score
    db.session.commit()
    
    return jsonify({
        'message': '题目批量创建成功',
        'questions': [q.to_dict() for q in created_questions],
        'total_score': total_score
    }), 201

@bp.route('/<int:question_id>', methods=['PUT'])
@jwt_required()
def update_question(question_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'teacher':
        return jsonify({'error': '只有老师可以修改题目'}), 403
    
    question = Question.query.get(question_id)
    if not question:
        return jsonify({'error': '题目不存在'}), 404
    
    assignment = Assignment.query.get(question.assignment_id)
    if assignment.teacher_id != user_id:
        return jsonify({'error': '无权操作此题目'}), 403
    
    data = request.get_json()
    
    if data.get('content'):
        question.content = data['content']
    if data.get('question_type'):
        question.question_type = data['question_type']
    if data.get('image_url') is not None:
        question.image_url = data['image_url']
    if data.get('options'):
        question.set_options(data['options'])
    if data.get('correct_answer') is not None:
        question.correct_answer = data['correct_answer']
    if data.get('score') is not None:
        question.score = data['score']
    if data.get('question_number') is not None:
        question.question_number = data['question_number']
    
    db.session.commit()
    
    return jsonify({
        'message': '题目更新成功',
        'question': question.to_dict()
    }), 200

@bp.route('/<int:question_id>', methods=['DELETE'])
@jwt_required()
def delete_question(question_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != 'teacher':
        return jsonify({'error': '只有老师可以删除题目'}), 403
    
    question = Question.query.get(question_id)
    if not question:
        return jsonify({'error': '题目不存在'}), 404
    
    assignment = Assignment.query.get(question.assignment_id)
    if assignment.teacher_id != user_id:
        return jsonify({'error': '无权操作此题目'}), 403
    
    db.session.delete(question)
    db.session.commit()
    
    return jsonify({'message': '题目删除成功'}), 200

@bp.route('/<int:question_id>/answers', methods=['GET'])
@jwt_required()
def get_question_answers(question_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    question = Question.query.get(question_id)
    if not question:
        return jsonify({'error': '题目不存在'}), 404
    
    assignment = Assignment.query.get(question.assignment_id)
    
    if user.role == 'teacher':
        if assignment.teacher_id != user_id:
            return jsonify({'error': '无权查看此题目的答案'}), 403
        answers = Answer.query.filter_by(question_id=question_id).all()
    else:
        submission = Submission.query.filter_by(
            assignment_id=assignment.id,
            student_id=user_id
        ).first()
        if not submission:
            return jsonify({'answers': []}), 200
        answers = Answer.query.filter_by(
            question_id=question_id,
            submission_id=submission.id
        ).all()
    
    return jsonify({
        'answers': [a.to_dict() for a in answers]
    }), 200
