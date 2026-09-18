"""Normal three-role functional journey, no external AI or load generation."""
from datetime import datetime, timedelta
import secrets
import unittest
from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import User
from config import TestingConfig


def exercise_teaching_flow(app):
    client = app.test_client()
    credentials, headers, steps = {}, {}, []

    def call(method, path, expected=200, role=None, **kwargs):
        result = client.open(path, method=method, headers=headers.get(role, {}), **kwargs)
        if result.status_code != expected:
            raise AssertionError(f'{method} {path}: expected {expected}, got {result.status_code}')
        steps.append({'method': method, 'path': path, 'status': result.status_code})
        return result.get_json()

    for role in ('teacher', 'student', 'admin'):
        password = secrets.token_urlsafe(18)
        username = 'smoke_' + role
        db.session.add(User(username=username, password=generate_password_hash(password),
                            name='本地验收' + role, email=role + '@smoke.invalid', role=role,
                            student_id='SMOKE01' if role == 'student' else None))
        credentials[role] = {'username': username, 'password': password, 'role': role}
    db.session.commit()
    for role, account in credentials.items():
        response = call('POST', '/api/auth/login', json=account)
        headers[role] = {'Authorization': 'Bearer ' + response['access_token']}
        call('GET', '/api/auth/me', role=role)
    course = call('POST', '/api/courses/create', 201, 'teacher', json={'name': '合成流程验收课程', 'class_name': '验收班'})['course']
    call('POST', '/api/courses/join', 201, 'student', json={'code': course['code']})
    assignment = call('POST', '/api/assignments', 201, 'teacher', json={
        'title': '合成流程验收作业', 'course_id': course['id'],
        'due_date': (datetime.utcnow() + timedelta(days=1)).isoformat(), 'total_score': 10})['assignment']
    question = call('POST', '/api/questions', 201, 'teacher', json={
        'assignment_id': assignment['id'], 'content': '请写出 Python 的一个特点',
        'question_type': 'text', 'score': 10, 'correct_answer': '语法简洁'})['question']
    call('GET', f'/api/assignments/{assignment["id"]}', role='student')
    submission = call('POST', f'/api/assignments/{assignment["id"]}/submit', role='student', json={
        'content': '流程测试答案', 'answers': [{'question_id': question['id'], 'answer_text': '语法简洁'}]})['submission']
    call('GET', f'/api/assignments/{assignment["id"]}/submissions', role='teacher')
    call('PUT', f'/api/assignments/submissions/{submission["id"]}/grade', role='teacher', json={'score': 9, 'feedback': '已完成本地功能演练'})
    result = call('GET', f'/api/assignments/{assignment["id"]}', role='student')
    assert result['assignment']['my_submission']['score'] == 9
    courses = call('GET', '/api/courses/my-courses', role='student')['courses']
    assert courses[0]['assignment_count'] == 1
    assert courses[0]['student_count'] == 1
    entry_id = call('POST', '/api/knowledge/entries', 201, 'student', json={
        'library': 'student', 'category': '其他', 'title': '合成图书馆说明',
        'content': '这是测试资料，不是真实学校政策。图书馆借书证挂失请到服务台。'})['id']
    call('POST', f'/api/knowledge/entries/{entry_id}/review', role='admin', json={'status': 'approved'})
    reply = call('POST', '/api/knowledge/assistant', role='student', json={'message': '借书证挂失', 'mode': 'local'})
    assert reply['sources'][0]['id'] == entry_id
    return steps, credentials


class TeachingFlowTests(unittest.TestCase):
    def test_three_role_normal_journey(self):
        app = create_app(TestingConfig)
        with app.app_context():
            try:
                steps, _ = exercise_teaching_flow(app)
                self.assertEqual(len(steps), 19)
            finally:
                db.session.remove()
                db.drop_all()
