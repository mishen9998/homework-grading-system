"""Real MySQL API/locking integration. Uses only newly generated t1_auth_* DBs.

Run with T1_MYSQL_SERVER_URL pointing at a disposable local MySQL server,
without a database component. No .env file is read.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Barrier, Event
from unittest.mock import patch
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token
from flask_migrate import upgrade
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import AuditLog, Organization, User
from app.services.organization_context import session_claims
from config import TestingConfig


@pytest.fixture()
def mysql_system():
    raw = os.environ.get('T1_MYSQL_SERVER_URL')
    if not raw:
        pytest.skip('requires isolated T1_MYSQL_SERVER_URL')
    server_url = make_url(raw)
    if (server_url.drivername != 'mysql+pymysql' or server_url.host not in ('127.0.0.1', 'localhost')
            or server_url.database):
        pytest.fail('T1 MySQL fixture requires a local disposable server URL without a database')
    name = 't1_auth_' + uuid4().hex
    server = create_engine(server_url, isolation_level='AUTOCOMMIT')
    with server.connect() as connection:
        connection.execute(text(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4'))

    class MySQLConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = server_url.set(database=name).render_as_string(hide_password=False)
        AUTO_CREATE_TABLES = False
        SECRET_KEY = 'isolated-mysql-auth-secret-key-at-least-32'
        JWT_SECRET_KEY = 'isolated-mysql-auth-jwt-key-at-least-32'
        REDIS_URL = ''
        QDRANT_URL = ''
        DEEPSEEK_API_KEY = ''
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True, 'pool_size': 5,
            'connect_args': {'init_command': 'SET SESSION innodb_lock_wait_timeout=10'},
        }

    try:
        with patch('app._setup_logging'):
            app = create_app(MySQLConfig)
        with app.app_context():
            upgrade(directory=str(Path(__file__).resolve().parents[1] / 'migrations'))
            org = Organization(code='locktest', name='Synthetic lock test', user_limit=2,
                               expires_at=datetime.utcnow() + timedelta(days=10))
            db.session.add(org)
            db.session.flush()
            admin = User(organization_id=org.id, username='admin', name='Admin', role='admin',
                         email='admin@test.invalid', password=generate_password_hash('Admin-password-123'))
            db.session.add(admin)
            db.session.commit()
            org_id, user_id = org.id, admin.id
            token = create_access_token(identity=str(admin.id), additional_claims=session_claims(admin))
        yield app, {'Authorization': 'Bearer ' + token}, org_id, user_id
    finally:
        if 'app' in locals():
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        # Only the exact random database created by this fixture is removed.
        assert name.startswith('t1_auth_') and len(name) == 40 and name[8:].isalnum()
        with server.connect() as connection:
            connection.execute(text(f'DROP DATABASE `{name}`'))
        server.dispose()


def test_last_account_slot_is_atomic_under_mysql_repeatable_read(mysql_system):
    app, token_headers, org_id, _ = mysql_system
    from app.routes.admin import lock_organization
    barrier = Barrier(2)

    def synchronized_lock(*args, **kwargs):
        # Both requests have already read identity/organization and established
        # their REPEATABLE READ snapshots before either acquires the row lock.
        barrier.wait(timeout=20)
        return lock_organization(*args, **kwargs)

    def create_student(index):
        with app.test_client() as client:
            response = client.post('/api/admin/users', headers=token_headers, json={
                'username': f'student{index}', 'name': f'Student {index}', 'role': 'student',
                'email': f'student{index}@test.invalid', 'password': 'Student-password-123'})
            return response.status_code, response.get_json()

    with patch('app.routes.admin.lock_organization', side_effect=synchronized_lock):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(create_student, [1, 2]))
    assert sorted(status for status, _ in results) == [201, 409], results
    assert [body['code'] for status, body in results if status == 409] == ['user_limit_exceeded']
    with app.app_context():
        assert User.query.filter_by(organization_id=org_id).count() == 2


def test_mysql_login_revocation_and_same_username_across_organizations(mysql_system):
    app, token_headers, org_id, user_id = mysql_system
    with app.app_context():
        other = Organization(code='other', name='Other')
        db.session.add(other)
        db.session.flush()
        db.session.add(User(organization_id=other.id, username='admin', name='Other Admin',
                            role='admin', email='admin@test.invalid',
                            password=generate_password_hash('Other-password-123')))
        db.session.commit()
    with app.test_client() as client:
        own = client.post('/api/auth/login', json={'organization_code': 'locktest',
                          'username': 'admin', 'password': 'Admin-password-123'})
        other = client.post('/api/auth/login', json={'organization_code': 'other',
                            'username': 'admin', 'password': 'Other-password-123'})
        assert own.status_code == other.status_code == 200
        assert own.json['user']['id'] == user_id
        assert other.json['user']['id'] != user_id
        assert client.get(f"/api/admin/users/{other.json['user']['id']}", headers=token_headers).status_code == 404
        with app.app_context():
            org = db.session.get(Organization, org_id)
            org.status = 'disabled'
            db.session.commit()
        denied = client.get('/api/admin/users', headers=token_headers)
        assert denied.status_code == 403
        assert denied.json['code'] == 'organization_disabled'


def test_admin_revoked_after_authentication_cannot_write_after_lock_wait(mysql_system):
    app, token_headers, org_id, user_id = mysql_system
    from app.routes.admin import lock_organization

    def revoke_then_lock(*args, **kwargs):
        # A separate committed transaction changes authorization after the
        # request's initial authenticated snapshot, just before its row lock.
        with db.engine.begin() as connection:
            connection.execute(text('UPDATE users SET is_active=0, token_version=token_version+1 '
                                    'WHERE id=:id'), {'id': user_id})
        return lock_organization(*args, **kwargs)

    with patch('app.routes.admin.lock_organization', side_effect=revoke_then_lock):
        with app.test_client() as client:
            response = client.post('/api/admin/users', headers=token_headers, json={
                'username': 'must-not-exist', 'email': 'no@test.invalid', 'name': 'No',
                'role': 'student', 'password': 'Student-password-123'})
    assert response.status_code == 401, response.get_json()
    assert response.json['code'] == 'stale_session'
    with app.app_context():
        assert User.query.filter_by(organization_id=org_id).count() == 1


def seed_platform(app):
    with app.app_context():
        organization = Organization.query.filter_by(code='platform').one()
        user = User(organization_id=organization.id, username='platform-operator',
                    name='Synthetic Platform', role='platform_admin', email='platform@test.invalid',
                    password=generate_password_hash('Platform-password-123'))
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id), additional_claims=session_claims(user))
        return organization.id, user.id, {'Authorization': 'Bearer ' + token}


@pytest.mark.parametrize('revocation,expected_status', [
    ('disabled_actor', 401), ('changed_role', 401), ('changed_version', 401),
    ('changed_organization', 401), ('disabled_platform', 403), ('expired_platform', 403),
])
def test_platform_customer_lock_wait_revalidates_identity_and_policy(mysql_system, revocation, expected_status):
    app, _, customer_id, _ = mysql_system
    platform_id, actor_id, token_headers = seed_platform(app)
    from app.routes.organizations import customer
    reached = Event()

    def wait_customer(*args, **kwargs):
        reached.set()
        return customer(*args, **kwargs)

    def update_customer():
        with app.test_client() as client:
            return client.put(f'/api/platform/organizations/{customer_id}',
                              headers=token_headers, json={'status': 'disabled'})

    with app.app_context():
        engine = db.engine
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text('SELECT id FROM organizations WHERE id=:id FOR UPDATE'), {'id': customer_id})
        with patch('app.routes.organizations.customer', side_effect=wait_customer), ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(update_customer)
            try:
                assert reached.wait(10)
                changes = {
                    'disabled_actor': ('UPDATE users SET is_active=0 WHERE id=:id', actor_id),
                    'changed_role': ("UPDATE users SET role='admin' WHERE id=:id", actor_id),
                    'changed_version': ('UPDATE users SET token_version=token_version+1 WHERE id=:id', actor_id),
                    'changed_organization': ('UPDATE users SET organization_id=:customer WHERE id=:id', actor_id),
                    'disabled_platform': ("UPDATE organizations SET status='disabled' WHERE id=:id", platform_id),
                    'expired_platform': ("UPDATE organizations SET expires_at='2000-01-01' WHERE id=:id", platform_id),
                }
                sql, row_id = changes[revocation]
                connection.execute(text(sql), {'id': row_id, 'customer': customer_id})
                transaction.commit()
            finally:
                if transaction.is_active:
                    transaction.rollback()
            response = future.result(timeout=10)
    assert response.status_code == expected_status, response.get_json()
    with app.app_context():
        assert db.session.get(Organization, customer_id).status == 'active'
        assert AuditLog.query.filter_by(action='organization.updated').count() == 0


def test_platform_creation_rechecks_actor_after_own_organization_lock_wait(mysql_system):
    app, _, _, _ = mysql_system
    platform_id, actor_id, token_headers = seed_platform(app)
    from app.routes.organizations import lock_current_identity
    reached = Event()

    def waiting_identity(*args, **kwargs):
        reached.set()
        return lock_current_identity(*args, **kwargs)

    def create_customer():
        with app.test_client() as client:
            return client.post('/api/platform/organizations', headers=token_headers, json={
                'code': 'must-not-open', 'name': 'Must not open',
                'admin': {'username': 'first-admin', 'email': 'first@test.invalid',
                          'name': 'First', 'password': 'First-password-123'}})

    with app.app_context():
        engine = db.engine
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text('SELECT id FROM organizations WHERE id=:id FOR UPDATE'), {'id': platform_id})
        with patch('app.routes.organizations.lock_current_identity', side_effect=waiting_identity), ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(create_customer)
            try:
                assert reached.wait(10)
                connection.execute(text('UPDATE users SET token_version=token_version+1 WHERE id=:id'), {'id': actor_id})
                transaction.commit()
            finally:
                if transaction.is_active:
                    transaction.rollback()
            response = future.result(timeout=10)
    assert response.status_code == 401, response.get_json()
    with app.app_context():
        assert Organization.query.filter_by(code='must-not-open').count() == 0
        assert User.query.filter_by(username='first-admin').count() == 0
        assert AuditLog.query.filter_by(action='organization.created').count() == 0


def test_delayed_logout_never_restores_token_revoked_by_password_reset(mysql_system):
    app, admin_headers, organization_id, _ = mysql_system
    with app.app_context():
        student = User(organization_id=organization_id, username='student', name='Student',
                       role='student', email='student@test.invalid',
                       password=generate_password_hash('Original-password-123'))
        db.session.add(student)
        db.session.commit()
        student_id = student.id
        token = create_access_token(identity=str(student_id), additional_claims=session_claims(student))
    student_headers = {'Authorization': 'Bearer ' + token}
    from app.routes.auth import current_user
    reached, release = Event(), Event()

    def paused_user():
        user = current_user()
        reached.set()
        assert release.wait(15)
        return user

    def logout():
        with app.test_client() as client:
            return client.post('/api/auth/logout', headers=student_headers)

    with patch('app.routes.auth.current_user', side_effect=paused_user), ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(logout)
        try:
            assert reached.wait(10)
            with app.test_client() as client:
                assert client.put(f'/api/admin/users/{student_id}', headers=admin_headers,
                                  json={'password': 'First-reset-123'}).status_code == 200
                login = client.post('/api/auth/login', json={'organization_code': 'locktest',
                                    'username': 'student', 'password': 'First-reset-123'})
                assert login.status_code == 200
                intermediate_headers = {'Authorization': 'Bearer ' + login.json['access_token']}
                assert client.put(f'/api/admin/users/{student_id}', headers=admin_headers,
                                  json={'password': 'Second-reset-123'}).status_code == 200
                # This cannot call auth.me until the patched current_user is released.
            with app.app_context():
                assert db.session.get(User, student_id).token_version == 3
        finally:
            release.set()
        response = future.result(timeout=10)
    assert response.status_code == 401, response.get_json()
    with app.app_context():
        assert db.session.get(User, student_id).token_version == 3
        assert AuditLog.query.filter_by(action='session.logout', target_id=str(student_id)).count() == 0
    with app.test_client() as client:
        assert client.get('/api/auth/me', headers=intermediate_headers).status_code == 401
        assert client.get('/api/auth/me', headers=student_headers).status_code == 401


def test_concurrent_logout_has_one_monotonic_revocation(mysql_system):
    app, token_headers, _, actor_id = mysql_system
    from app.routes.auth import current_user
    barrier = Barrier(2)

    def simultaneous_user():
        user = current_user()
        barrier.wait(timeout=10)
        return user

    def logout(_):
        with app.test_client() as client:
            return client.post('/api/auth/logout', headers=token_headers).status_code

    with patch('app.routes.auth.current_user', side_effect=simultaneous_user), ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(logout, [1, 2]))
    assert sorted(statuses) == [200, 401]
    with app.app_context():
        assert db.session.get(User, actor_id).token_version == 2
        assert AuditLog.query.filter_by(action='session.logout', target_id=str(actor_id)).count() == 1
