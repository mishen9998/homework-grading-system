"""Database-aware grading tasks executed by the dedicated AI worker."""
import os

from app import db
from app.models import Answer, Assignment, Question, Submission, User
from app.services import DeepSeekService


def _teacher_assignment(user_id, assignment_id):
    assignment = db.session.get(Assignment, int(assignment_id))
    if not assignment or assignment.teacher_id != int(user_id):
        raise ValueError('作业不存在或无权操作')
    return assignment


def _friendly_error(result, default):
    error = result.get('error', default)
    if '402' in error or 'Insufficient Balance' in error:
        return 'DeepSeek账户余额不足，请联系管理员检查模型账户余额'
    return error


def _grade_text(payload):
    question = db.session.get(Question, int(payload['question_id']))
    submission = db.session.get(Submission, int(payload['submission_id']))
    if not question or not submission or submission.assignment_id != question.assignment_id:
        raise ValueError('题目或提交不存在')
    _teacher_assignment(payload['user_id'], question.assignment_id)
    answer = Answer.query.filter_by(submission_id=submission.id, question_id=question.id).first()
    if not answer:
        raise ValueError('未找到学生答案')
    result = DeepSeekService.grade_text_question(
        question_content=question.content, question_score=question.score,
        reference_answer=question.correct_answer, student_answer=answer.answer_text)
    if not result.get('success'):
        return {'success': False, 'error': _friendly_error(result, 'AI评分失败')}
    answer.score = result['score']
    answer.feedback = result.get('feedback', '')
    answer.is_correct = result['score'] == question.score
    db.session.commit()
    return {'success': True, 'score': result['score'], 'feedback': answer.feedback,
            'analysis': result.get('analysis', ''), 'answer': answer.to_dict()}


def _student_code(submission, answer):
    if answer.answer_text:
        return answer.answer_text
    if submission.file_url and submission.file_url.endswith('.py'):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tupian',
                            submission.file_url.rsplit('/', 1)[-1])
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as stream:
                return stream.read()
    return ''


def _grade_python(payload):
    question = db.session.get(Question, int(payload['question_id']))
    submission = db.session.get(Submission, int(payload['submission_id']))
    if not question or not submission or submission.assignment_id != question.assignment_id:
        raise ValueError('题目或提交不存在')
    _teacher_assignment(payload['user_id'], question.assignment_id)
    answer = Answer.query.filter_by(submission_id=submission.id, question_id=question.id).first()
    if not answer:
        raise ValueError('未找到学生答案')
    code = _student_code(submission, answer)
    if not code:
        return {'success': False, 'error': '学生未提交代码'}
    result = DeepSeekService.grade_python_code(
        question_content=question.content, question_score=question.score,
        reference_answer=question.correct_answer, student_code=code, requirements=None)
    if not result.get('success'):
        return {'success': False, 'error': _friendly_error(result, 'AI评分失败')}
    answer.score = result['score']
    answer.feedback = result.get('feedback', '')
    answer.is_correct = result['score'] == question.score
    db.session.commit()
    return {'success': True, 'score': result['score'], 'feedback': answer.feedback,
            'code_analysis': result.get('code_analysis', {}),
            'improved_code': result.get('improved_code', ''), 'answer': answer.to_dict()}


def _overall_comment(payload):
    submission = db.session.get(Submission, int(payload['submission_id']))
    if not submission:
        raise ValueError('提交不存在')
    assignment = _teacher_assignment(payload['user_id'], submission.assignment_id)
    if submission.comment_locked:
        raise ValueError('评语已锁定，无法重新生成')
    questions = Question.query.filter_by(assignment_id=assignment.id).all()
    answers = {item.question_id: item for item in
               Answer.query.filter_by(submission_id=submission.id).all()}
    type_names = {'single_choice': '单选题', 'multiple_choice': '多选题',
                  'fill_blank': '填空题', 'true_false': '判断题', 'text': '大题'}
    rows = [{'type': type_names.get(q.question_type, '未知题型'),
             'score': answers[q.id].score if q.id in answers else 0,
             'max_score': q.score,
             'feedback': answers[q.id].feedback if q.id in answers else ''}
            for q in questions]
    student = db.session.get(User, submission.student_id)
    result = DeepSeekService.generate_overall_comment(
        assignment_title=assignment.title, student_name=student.name if student else None,
        total_score=submission.score or 0, max_score=assignment.total_score or 100,
        question_results=rows)
    if not result.get('success'):
        return {'success': False, 'error': _friendly_error(result, 'AI生成总评失败')}
    submission.overall_comment = result['comment']
    db.session.commit()
    return {'success': True, 'comment': result['comment'], 'submission': submission.to_dict()}


def _parse_questions(payload):
    from app.services.ai_parser import AIQuestionParser

    assignment = _teacher_assignment(payload['user_id'], payload['assignment_id'])
    result = AIQuestionParser.parse_questions(payload['text'])
    if not result.get('success'):
        return {'success': False, 'error': result.get('error', 'AI解析失败')}
    parsed = result.get('questions') or []
    if not parsed:
        return {'success': False, 'error': 'AI未能识别出有效题目'}
    number = Question.query.filter_by(assignment_id=assignment.id).count() + 1
    response_rows = []
    for raw in parsed:
        question = Question(assignment_id=assignment.id, question_number=number,
                            question_type=raw['question_type'], content=raw['content'],
                            score=raw['score'], correct_answer=raw.get('correct_answer', ''))
        if raw.get('options') and any(raw['options'].values()):
            question.set_options(raw['options'])
        db.session.add(question)
        number += 1
        response_rows.append({
            'question_type': raw['question_type'], 'content': raw['content'],
            'score': raw['score'], 'correct_answer': raw.get('correct_answer', ''),
            'options': raw.get('options', {'A': '', 'B': '', 'C': '', 'D': ''})})
    db.session.commit()
    return {'success': True, 'message': f'AI成功解析并导入 {len(response_rows)} 道题目',
            'success_count': len(response_rows), 'error_count': 0, 'questions': response_rows}


def execute_grading_task(kind, payload):
    handlers = {'grade_text': _grade_text, 'grade_python': _grade_python,
                'overall_comment': _overall_comment, 'parse_questions': _parse_questions}
    handler = handlers.get(kind)
    if not handler:
        raise ValueError('不支持的批改任务')
    return handler(payload)
