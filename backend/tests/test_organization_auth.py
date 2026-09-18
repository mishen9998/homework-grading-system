"""Synthetic authentication/policy regression tests, without real services."""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import Course, Organization, User
from app.services.organization_context import (
    PolicyError, check_organization_policy, require_organization_id, session_claims,
)
from config import TestingConfig


@pytest.fixture()
def system():
    class IsolatedConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        SECRET_KEY = 'isolated-auth-test-secret-key-at-least-32'
        JWT_SECRET_KEY = 'isolated-auth-test-jwt-secret-key-at-least-32'
        REDIS_URL = ''
        QDRANT_URL = ''
        DEEPSEEK_API_KEY = ''
    with patch('app._setup_logging'):
        app = create_app(IsolatedConfig)
    with app.app_context():
        a = Organization(code='a', name='A')
        b = Organization(code='b', name='B')
        platform = Organization(code='platform', name='Platform')
        db.session.add_all([a, b, platform])
        db.session.flush()
        users = {}
        for code, role in [('a', 'student'), ('a', 'teacher'), ('a', 'admin'),
                           ('b', 'student'), ('platform', 'platform_admin')]:
            org = {'a': a, 'b': b, 'platform': platform}[code]
            user = User(organization_id=org.id, username=role, name=role,
                        email=role + '@test.invalid', role=role,
                        password=generate_password_hash('Test-password-123'))
            db.session.add(user)
            users[(code, role)] = user
        db.session.commit()
        yield app, app.test_client(), {'a': a, 'b': b, 'platform': platform}, users
        db.session.remove()
        db.drop_all()


def headers(user, **overrides):
    claims = session_claims(user)
    claims.update(overrides)
    return {'Authorization': 'Bearer ' + create_access_token(identity=str(user.id),
                                                            additional_claims=claims)}


def test_login_requires_code_and_org_local_username(system):
    app, client, orgs, users = system
    base = {'username': 'student', 'password': 'Test-password-123'}
    assert client.post('/api/auth/login', json=base).status_code == 400
    for code in ('a', 'b'):
        response = client.post('/api/auth/login', json={**base, 'organization_code': code})
        assert response.status_code == 200
        assert response.json['user']['id'] == users[(code, 'student')].id
        assert response.json['organization']['id'] == orgs[code].id
    assert client.post('/api/auth/login', json={**base, 'organization_code': 'missing'}).status_code == 401
    assert client.post('/api/auth/login', json={**base, 'organization_code': 'a',
                                               'organization_id': orgs['b'].id}).status_code == 400


def test_public_registration_cannot_choose_identity(system):
    app, client, orgs, users = system
    app.config['PUBLIC_REGISTRATION'] = True
    for role in ('student', 'teacher', 'admin', 'platform_admin'):
        assert client.post('/api/auth/register', json={'role': role,
                     'organization_id': orgs['a'].id}).status_code == 403
    assert User.query.count() == len(users)


def test_old_forged_and_changed_claims_are_rejected(system):
    _, client, orgs, users = system
    student = users[('a', 'student')]
    old = create_access_token(identity=str(student.id), additional_claims={'role': 'student'})
    for token_headers in ({'Authorization': 'Bearer ' + old},
                          headers(student, organization_id=orgs['b'].id),
                          headers(student, role='admin'), headers(student, token_version=999)):
        response = client.get('/api/auth/me', headers=token_headers)
        assert response.status_code == 401
        assert response.json['code'] == 'stale_session'
    valid_headers = headers(student)
    student.role = 'teacher'
    db.session.commit()
    assert client.get('/api/auth/me', headers=valid_headers).status_code == 401


@pytest.mark.parametrize('mutation', ['disabled_account', 'deleted_account', 'moved_account'])
def test_current_database_identity_is_required_on_every_request(system, mutation):
    _, client, orgs, users = system
    user = users[('a', 'student')]
    token_headers = headers(user)
    if mutation == 'disabled_account':
        user.is_active = False
    elif mutation == 'deleted_account':
        db.session.delete(user)
    else:
        user.organization_id = orgs['b'].id
        user.username = 'moved'
        user.email = 'moved@test.invalid'
    db.session.commit()
    for path in ('/api/auth/me', '/api/assignments', '/api/courses/my-courses'):
        assert client.get(path, headers=token_headers).status_code == 401


def test_expiry_is_read_only_but_disable_denies_business(system):
    _, client, orgs, users = system
    user = users[('a', 'student')]
    token_headers = headers(user)
    orgs['a'].expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.session.commit()
    assert client.get('/api/auth/me', headers=token_headers).json['read_only'] is True
    assert client.get('/api/assignments', headers=token_headers).status_code == 200
    for path, body in [('/api/knowledge/entries', {'title': 'x'}),
                       ('/api/knowledge/assistant', {'message': 'x', 'mode': 'deepseek'})]:
        response = client.post(path, headers=token_headers, json=body)
        assert response.status_code == 403
        assert response.json['code'] == 'organization_expired'
    with patch('app.routes.knowledge.retrieve', return_value=([], [])) as local:
        response = client.post('/api/knowledge/assistant', headers=token_headers,
                               json={'message': 'local history', 'mode': 'local'})
        assert response.status_code == 200
        local.assert_called_once()
    orgs['a'].status = 'disabled'
    db.session.commit()
    for method, path, body in [('GET', '/api/auth/me', None),
                                ('GET', '/api/assignments', None),
                                ('POST', '/api/knowledge/assistant', {'message': 'local'})]:
        response = client.open(path, method=method, headers=token_headers, json=body)
        assert response.status_code == 403
        assert response.json['code'] == 'organization_disabled'
    assert client.post('/api/auth/login', json={'organization_code': 'a',
                        'username': 'student', 'password': 'Test-password-123'}).status_code == 403


def test_management_fields_cannot_be_self_edited(system):
    _, client, orgs, users = system
    student = users[('a', 'student')]
    protected = {'role': 'admin', 'student_id': '999', 'teacher_id': 'staff',
                 'class_name': 'another', 'organization_class_id': 42,
                 'organization_id': orgs['b'].id, 'username': 'admin',
                 'is_active': True, 'token_version': 50, 'college': 'another'}
    for field, value in protected.items():
        response = client.put('/api/auth/update-profile', headers=headers(student),
                              json={field: value, 'name': 'must not change'})
        assert response.status_code == 403
        assert db.session.get(User, student.id).name == 'student'
    response = client.put('/api/auth/update-profile', headers=headers(student),
                          json={'name': 'New display name', 'phone': '123'})
    assert response.status_code == 200
    assert response.json['user']['phone'] == '123'


def test_platform_cannot_read_business_and_tenant_cannot_admin_platform(system):
    _, client, _, users = system
    token_headers = headers(users[('platform', 'platform_admin')])
    assert client.get('/api/auth/me', headers=token_headers).status_code == 200
    for path in ('/api/assignments', '/api/courses/my-courses', '/api/knowledge/entries',
                 '/api/admin/users', '/api/schedules/student'):
        response = client.get(path, headers=token_headers)
        assert response.status_code == 403
        assert response.json['code'] == 'platform_business_denied'
    assert client.get('/api/platform/organizations', headers=headers(users[('a', 'admin')])).status_code == 403


def test_logout_revokes_existing_session(system):
    _, client, _, users = system
    token_headers = headers(users[('a', 'student')])
    assert client.post('/api/auth/logout', headers=token_headers).status_code == 200
    assert client.get('/api/auth/me', headers=token_headers).status_code == 401


def test_ai_disabled_policy_and_worker_recheck(system):
    _, client, orgs, users = system
    teacher = users[('a', 'teacher')]
    with patch('app.services.deepseek_service.DeepSeekService._call_deepseek') as provider:
        for path in ('/api/ai/assistant', '/api/assignments/ai-grade', '/api/assignments/ai-test'):
            response = client.post(path, headers=headers(teacher), json={})
            assert response.status_code == 403
            assert response.json['code'] == 'ai_not_authorized'
        provider.assert_not_called()
    with pytest.raises(PolicyError, match='机构尚未授权'):
        check_organization_policy(teacher, orgs['a'], external_ai=True)
    orgs['a'].ai_enabled = True
    db.session.commit()
    assert check_organization_policy(teacher, orgs['a'], external_ai=True).id == orgs['a'].id
    orgs['a'].status = 'disabled'
    db.session.commit()
    with pytest.raises(PolicyError, match='机构已停用'):
        check_organization_policy(teacher, orgs['a'], external_ai=True)


def test_offline_creation_requires_explicit_organization(system):
    with pytest.raises(PolicyError, match='显式指定'):
        require_organization_id()


def test_platform_role_cannot_be_attached_to_customer_account(system):
    _, client, _, users = system
    user = users[('a', 'admin')]
    user.role = 'platform_admin'
    db.session.commit()
    response = client.get('/api/platform/organizations', headers=headers(user))
    assert response.status_code == 403
    assert response.json['code'] == 'invalid_platform_identity'


def test_new_business_row_uses_server_organization(system):
    _, client, orgs, users = system
    response = client.post('/api/courses/create', headers=headers(users[('a', 'teacher')]),
                           json={'name': 'Synthetic course', 'organization_id': orgs['b'].id})
    assert response.status_code == 201
    row = db.session.get(Course, response.json['course']['id'])
    assert row.organization_id == orgs['a'].id
