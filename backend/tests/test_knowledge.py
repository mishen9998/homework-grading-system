import io
import json
import unittest
from unittest.mock import patch
from flask_jwt_extended import create_access_token
from app import create_app, db
from app.models import Assignment, Course, CourseEnrollment, Message, User
from config import TestingConfig


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        class MemoryConfig(TestingConfig):
            SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        self.app = create_app(MemoryConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        self.headers = {}
        for name, role in [('student', 'student'), ('peer', 'student'), ('teacher', 'teacher'), ('admin', 'admin')]:
            user = User(username=name, password='unused', email=name+'@test.local', name=name, role=role)
            db.session.add(user)
            db.session.flush()
            self.headers[name] = {'Authorization': 'Bearer ' + create_access_token(identity=str(user.id))}
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def submit(self, role='student', title='图书馆楼层', content='图书馆位于三楼。'):
        result = self.client.post('/api/knowledge/entries', headers=self.headers[role], data={
            'library': role, 'title': title, 'content': content,
            'category': '楼层导览' if role == 'student' else '学校信息',
            'file': (io.BytesIO(b'private document'), 'guide.txt')})
        self.assertEqual(result.status_code, 201)
        return result.json['id']

    def review(self, entry_id, status='approved', note=''):
        return self.client.post(f'/api/knowledge/entries/{entry_id}/review', headers=self.headers['admin'],
                                json={'status': status, 'review_note': note})

    def test_approval_visibility_and_attachment_permissions(self):
        entry_id = self.submit()
        endpoint = f'/api/knowledge/entries/{entry_id}'
        self.assertEqual(self.client.get('/api/knowledge/entries', headers=self.headers['peer']).json['total'], 0)
        for suffix in ['', '/attachment']:
            self.assertEqual(self.client.get(endpoint+suffix, headers=self.headers['peer']).status_code, 404)
            self.assertEqual(self.client.get(endpoint+suffix, headers=self.headers['teacher']).status_code, 403)
            self.assertEqual(self.client.get(endpoint+suffix, headers=self.headers['student']).status_code, 200)
        self.assertEqual(self.client.post(endpoint+'/review', headers=self.headers['student'], json={'status': 'approved'}).status_code, 403)
        review = self.review(entry_id)
        self.assertEqual(review.status_code, 200)
        self.assertTrue(review.json['semantic_indexed'])
        self.assertEqual(self.review(entry_id).status_code, 409)
        self.assertEqual(self.client.get('/api/knowledge/entries', headers=self.headers['peer']).json['total'], 1)
        self.assertEqual(self.client.get(endpoint+'/attachment', headers=self.headers['peer']).data, b'private document')
        status = self.client.get('/api/knowledge/embeddings/status', headers=self.headers['admin'])
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json['approved'], 1)
        self.assertEqual(status.json['indexed'], 1)

    def test_rejection_and_role_spoofing(self):
        entry_id = self.submit()
        self.assertEqual(self.review(entry_id, 'rejected').status_code, 400)
        self.assertEqual(self.review(entry_id, 'rejected', '请核实楼层').status_code, 200)
        own = self.client.get('/api/knowledge/entries?mine=true', headers=self.headers['student']).json['items'][0]
        self.assertEqual(own['review_note'], '请核实楼层')
        self.assertEqual(self.client.get('/api/knowledge/entries?library=teacher', headers=self.headers['student']).status_code, 403)
        self.assertEqual(self.client.post('/api/knowledge/entries', headers=self.headers['student'], json={'library': 'teacher'}).status_code, 403)
        self.assertEqual(self.client.get('/api/knowledge/libraries', headers=self.headers['teacher']).json[0]['id'], 'teacher')
        self.assertEqual(self.client.get('/api/knowledge/libraries').status_code, 401)

    @patch('app.services.ai_tasks.DeepSeekService._call_deepseek')
    def test_ai_uses_only_approved_role_sources(self, call):
        self.submit(title='图书馆未审核', content='保密待审资料')
        rejected = self.submit(title='图书馆驳回', content='错误资料')
        self.review(rejected, 'rejected', '错误')
        teacher = self.submit('teacher', content='教师专属信息')
        self.review(teacher)
        endpoint = '/api/knowledge/assistant'
        result = self.client.post(endpoint, headers=self.headers['student'], json={'message': '图书馆在哪层？'})
        self.assertEqual(result.json['sources'], [])
        call.assert_not_called()
        approved = self.submit()
        self.review(approved)
        call.return_value = {'success': True, 'content': '图书馆在三楼。'}
        result = self.client.post(endpoint, headers=self.headers['student'], json={'message': '图书馆在哪层？'})
        self.assertEqual([s['id'] for s in result.json['sources']], [approved])
        self.assertEqual(result.json['mode'], 'local')
        self.assertIn('图书馆位于三楼', result.json['reply'])
        self.assertTrue(result.json['can_deepen'])
        call.assert_not_called()
        result = self.client.post(endpoint, headers=self.headers['student'], json={'message': '图书馆在哪层？', 'mode': 'deepseek'})
        self.assertEqual(result.json['mode'], 'deepseek')
        call.assert_called_once()
        prompt = json.loads(call.call_args.args[0][1]['content'])
        self.assertEqual([e['id'] for e in prompt['参考资料']], [approved])
        call.return_value = {'success': False}
        self.assertTrue(self.client.post(endpoint, headers=self.headers['student'], json={'message': '图书馆', 'mode': 'deepseek'}).json['degraded'])

    @patch('app.services.ai_tasks.DeepSeekService._call_deepseek')
    def test_teacher_local_and_empty_deep_query_never_call_model(self, call):
        entry_id = self.submit('teacher', content='教师图书馆位于五楼。')
        self.review(entry_id)
        result = self.client.post('/api/knowledge/assistant', headers=self.headers['teacher'],
                                  json={'message': '图书馆'})
        self.assertEqual(result.json['mode'], 'local')
        self.assertIn('五楼', result.json['reply'])
        empty = self.client.post('/api/knowledge/assistant', headers=self.headers['student'],
                                 json={'message': '图书馆', 'mode': 'deepseek'})
        self.assertEqual(empty.json['sources'], [])
        self.assertFalse(empty.json['can_deepen'])
        call.assert_not_called()

    def test_invalid_inputs(self):
        for payload in [[], {'message': 3}, {'message': ''}, {'message': '图书馆', 'mode': 'invalid'}]:
            self.assertEqual(self.client.post('/api/knowledge/assistant', headers=self.headers['student'], json=payload).status_code, 400)
        data = {'title': '课程', 'category': '线上课程', 'content': '课程介绍', 'source_url': 'javascript:alert(1)'}
        self.assertEqual(self.client.post('/api/knowledge/entries', headers=self.headers['student'], json=data).status_code, 400)

    def test_hybrid_retrieval_handles_rephrasing(self):
        entry_id = self.submit(title='宿舍晚归处理规定', content='学生夜间回寝超过规定时间，将按照宿舍管理办法进行处分。')
        self.assertEqual(self.review(entry_id).status_code, 200)
        result = self.client.post('/api/knowledge/assistant', headers=self.headers['student'],
                                  json={'message': '夜间回寝太晚会有什么惩罚？'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['sources'][0]['id'], entry_id)
        self.assertGreater(result.json['sources'][0]['semantic_score'], 0)

    @patch('app.services.ai_tasks.DeepSeekService._call_deepseek')
    def test_external_ai_redacts_common_personal_identifiers(self, call):
        entry_id = self.submit(title='图书馆联系方式',
                               content='图书馆电话为13800138000，邮箱为library@example.com。')
        self.review(entry_id)
        call.return_value = {'success': True, 'content': '已根据资料回答。'}
        result = self.client.post('/api/knowledge/assistant', headers=self.headers['student'], json={
            'message': '我的身份证号是110101199001011234，请问图书馆电话？', 'mode': 'deepseek'})
        self.assertEqual(result.status_code, 200)
        outbound = call.call_args.args[0][1]['content']
        self.assertNotIn('110101199001011234', outbound)
        self.assertNotIn('13800138000', outbound)
        self.assertNotIn('library@example.com', outbound)
        self.assertEqual(set(result.json['privacy_redacted']), {'身份证号', '手机号', '电子邮箱'})

    def test_per_user_assistant_rate_limit(self):
        user = User(username='limited', password='unused', email='limited@test.local',
                    name='limited', role='student')
        db.session.add(user)
        db.session.commit()
        headers = {'Authorization': 'Bearer ' + create_access_token(identity=str(user.id))}
        self.app.config['KNOWLEDGE_QUERY_RATE_LIMIT'] = 1
        endpoint = '/api/knowledge/assistant'
        self.assertEqual(self.client.post(endpoint, headers=headers, json={'message': '图书馆'}).status_code, 200)
        limited = self.client.post(endpoint, headers=headers, json={'message': '图书馆'})
        self.assertEqual(limited.status_code, 429)
        self.assertIn('Retry-After', limited.headers)

    @patch('app.services.knowledge_search.search_entry_ids')
    def test_vector_candidates_are_filtered_by_role_library(self, vector_search):
        teacher_entry = self.submit('teacher', title='教师内部安排', content='教师内部资料。')
        self.review(teacher_entry)
        vector_search.return_value = [teacher_entry]
        result = self.client.post('/api/knowledge/assistant', headers=self.headers['student'],
                                  json={'message': '教师内部安排'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['sources'], [])

    def test_permission_agent_can_preview_and_publish_teacher_assignment(self):
        course = Course(name='测试课程', code='AGENT01', teacher_id=User.query.filter_by(username='teacher').first().id,
                        description='测试', class_name='测试班', expected_students=1)
        db.session.add(course)
        db.session.commit()
        agent_url = '/api/knowledge/agent'
        preview = self.client.post(agent_url, headers=self.headers['teacher'], json={'message': '生成测试课程作业'})
        self.assertEqual(preview.status_code, 200)
        action = preview.json['action']
        self.assertEqual(action['type'], 'publish_assignment')
        published = self.client.post(agent_url, headers=self.headers['teacher'], json={
            'message': '确认执行', 'confirm': True, 'action': action['type'], 'payload': action['payload']})
        self.assertEqual(published.status_code, 200)
        self.assertEqual(Assignment.query.filter_by(course_id=course.id).count(), 1)
        student = User.query.filter_by(username='student').first()
        db.session.add(CourseEnrollment(course_id=course.id, student_id=student.id))
        db.session.commit()
        reminder = self.client.post(agent_url, headers=self.headers['teacher'], json={'message': '提醒测试课程未提交'})
        self.assertEqual(reminder.status_code, 200)
        reminder_action = reminder.json['action']
        self.assertEqual(reminder_action['type'], 'send_reminder')
        sent = self.client.post(agent_url, headers=self.headers['teacher'], json={
            'message': '确认执行', 'confirm': True, 'action': reminder_action['type'], 'payload': reminder_action['payload']})
        self.assertEqual(sent.status_code, 200)
        self.assertEqual(Message.query.filter_by(receiver_id=student.id, related_course_id=course.id).count(), 1)
        denied = self.client.post(agent_url, headers=self.headers['student'], json={
            'message': '确认执行', 'confirm': True, 'action': action['type'], 'payload': action['payload']})
        self.assertEqual(denied.status_code, 403)

    def test_student_agent_reads_only_enrolled_courses(self):
        student = User.query.filter_by(username='student').first()
        course = Course(name='学生测试课', code='AGENT02', teacher_id=User.query.filter_by(username='teacher').first().id,
                        description='测试', class_name='测试班', expected_students=1)
        db.session.add(course)
        db.session.flush()
        db.session.add(CourseEnrollment(course_id=course.id, student_id=student.id))
        db.session.commit()
        result = self.client.post('/api/knowledge/agent', headers=self.headers['student'], json={'message': '查看我的课程'})
        self.assertEqual(result.status_code, 200)
        self.assertIn('学生测试课', result.json['reply'])


if __name__ == '__main__':
    unittest.main()
