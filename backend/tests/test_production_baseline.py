import unittest
from flask_jwt_extended import create_access_token
from app import create_app, db
from app.models import User
from config import TestingConfig


class ProductionBaselineTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_public_admin_registration_denied(self):
        result = self.client.post('/api/auth/register', json={
            'username': 'intruder', 'password': 'test-password', 'name': 'Test', 'role': 'admin'})
        self.assertEqual(result.status_code, 403)
        self.assertEqual(User.query.count(), 0)

    def test_closed_registration(self):
        self.app.config['PUBLIC_REGISTRATION'] = False
        self.assertEqual(self.client.post('/api/auth/register', json={}).status_code, 403)

    def test_stale_admin_token_denied(self):
        user = User(username='former-admin', password='unused', email='test@example.com',
                    name='Test', role='student')
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id), additional_claims={'role': 'admin'})
        result = self.client.get('/api/admin/users', headers={'Authorization': 'Bearer ' + token})
        self.assertEqual(result.status_code, 403)

    def test_weak_production_secret_denied(self):
        class WeakConfig(TestingConfig):
            TESTING = False
            DEBUG = False
        with self.assertRaises(RuntimeError):
            create_app(WeakConfig)


if __name__ == '__main__':
    unittest.main()
