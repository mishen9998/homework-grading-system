"""Migration proofs on synthetic databases only; no dotenv or real model provider.

Optional MySQL: T1_SCHEMA_TEST_MYSQL_URL=mysql+pymysql://...@127.0.0.1:port/
Each case creates a random t1_schema_* database on that explicit loopback server.
"""
from datetime import datetime
import json
import os
from pathlib import Path
import re
import uuid

import pytest
import sqlalchemy as sa
from flask import Flask
from flask_migrate import Migrate, stamp, upgrade

from app import db
from app import models
from migrations.schema_support import BUSINESS_TABLES, legacy_metadata, migration_issues, preflight_database

MIGRATIONS = str(Path(__file__).resolve().parents[1] / 'migrations')


@pytest.fixture(params=['sqlite', 'mysql'])
def migration_app(request, tmp_path):
    admin_engine = None
    database = None
    if request.param == 'mysql':
        value = os.environ.get('T1_SCHEMA_TEST_MYSQL_URL')
        if not value:
            pytest.skip('Explicit isolated MySQL URL not supplied')
        url = sa.engine.make_url(value)
        assert url.host in ('127.0.0.1', 'localhost') and not url.database
        database = 't1_schema_' + uuid.uuid4().hex
        assert re.fullmatch(r't1_schema_[0-9a-f]{32}', database)
        admin_engine = sa.create_engine(url, isolation_level='AUTOCOMMIT')
        with admin_engine.connect() as connection:
            connection.execute(sa.text(f'CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'))
        uri = url.set(database=database).render_as_string(hide_password=False)
    else:
        uri = 'sqlite:///' + str(tmp_path / 'synthetic.db')
    application = Flask(__name__)
    application.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI=uri,
                              SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(application)
    Migrate(application, db)
    with application.app_context():
        yield application
        db.session.remove()
        db.engine.dispose()
    if admin_engine is not None:
        # Only the exact random database created by this fixture is removed.
        with admin_engine.connect() as connection:
            connection.execute(sa.text(f'DROP DATABASE `{database}`'))
        admin_engine.dispose()


def seed_legacy(*, chunks=False):
    metadata = legacy_metadata(include_knowledge=True, include_chunks=chunks)
    metadata.create_all(db.engine)  # A frozen historical fixture, never the application schema.
    now = datetime.utcnow()
    with db.engine.begin() as connection:
        connection.execute(metadata.tables['users'].insert(), [
            dict(id=10, username='admin', password='synthetic', email='admin@example.invalid', role='admin', name='Admin', class_name='Class A'),
            dict(id=20, username='teacher', password='synthetic', email='teacher@example.invalid', role='teacher', name='Teacher', class_name='Class A'),
            dict(id=30, username='student', password='synthetic', email='student@example.invalid', role='student', name='Student', class_name='Class A')])
        connection.execute(metadata.tables['courses'].insert().values(id=7, name='Synthetic course', code='SYNTH1', teacher_id=20, class_name='Class A'))
        connection.execute(metadata.tables['assignments'].insert().values(id=8, title='Synthetic work', teacher_id=20, course_id=7, due_date=now))
        connection.execute(metadata.tables['submissions'].insert().values(id=9, assignment_id=8, student_id=30, content='synthetic only'))
        connection.execute(metadata.tables['questions'].insert().values(id=11, assignment_id=8, question_number=1, question_type='text', content='Synthetic question'))
        connection.execute(metadata.tables['answers'].insert().values(id=12, submission_id=9, question_id=11, answer_text='Synthetic answer'))
        connection.execute(metadata.tables['knowledge_entries'].insert().values(id=13, library='student', category='guide', title='Synthetic guide', content='Synthetic source', source_url='', author_id=20, status='approved', review_note='', created_at=now))
        if chunks:
            connection.execute(metadata.tables['knowledge_chunks'].insert().values(id=14, entry_id=13, library='student', chunk_index=0, content='Synthetic source', content_hash='a'*64, embedding=b'1234', embedding_dim=1, embedding_model='synthetic', embedded_at=now))


def assert_current_schema():
    inspector = sa.inspect(db.engine)
    assert set(db.metadata.tables).issubset(inspector.get_table_names())
    for table in db.metadata.sorted_tables:
        actual = {c['name']: c for c in inspector.get_columns(table.name)}
        assert set(actual) == set(table.c.keys()), table.name
        for column in table.c:
            assert actual[column.name]['nullable'] == column.nullable, (table.name, column.name)
    for table in BUSINESS_TABLES:
        assert any(fk['constrained_columns'] == ['organization_id'] and
                   fk['referred_table'] == 'organizations' for fk in inspector.get_foreign_keys(table))
    unique = {tuple(item['column_names']) for item in inspector.get_unique_constraints('users')}
    assert ('organization_id', 'username') in unique and ('organization_id', 'email') in unique
    assert ('username',) not in unique and ('email',) not in unique
    with db.engine.connect() as connection:
        assert connection.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one() == 'd10a00100001'
        assert not migration_issues(connection)


def test_empty_database_complete_chain_and_repeat(migration_app):
    upgrade(directory=MIGRATIONS)
    assert_current_schema()
    upgrade(directory=MIGRATIONS)
    assert_current_schema()
    assert models.Organization.query.filter_by(code='platform').count() == 1
    assert models.User.query.filter_by(role='platform_admin').count() == 0


@pytest.mark.parametrize('legacy_revision,chunks', [(None, True), ('c37a9b4102fe', False)])
def test_history_preserves_identity_and_backfills_without_privilege_escalation(migration_app, legacy_revision, chunks):
    seed_legacy(chunks=chunks)
    if legacy_revision:
        stamp(directory=MIGRATIONS, revision=legacy_revision)
    upgrade(directory=MIGRATIONS)
    assert_current_schema()
    default = models.Organization.query.filter_by(code='default').one()
    user = db.session.get(models.User, 10)
    assert user.role == 'admin' and user.organization_id == default.id
    assert user.is_active and user.token_version == 1
    assert user.organization_class.name == 'Class A' and user.class_name == 'Class A'
    assert db.session.get(models.Answer, 12).answer_text == 'Synthetic answer'
    assert db.session.get(models.KnowledgeEntry, 13).content == 'Synthetic source'
    if chunks:
        assert db.session.get(models.KnowledgeChunk, 14).organization_id == default.id
    platform = models.Organization.query.filter_by(code='platform').one()
    db.session.add(models.User(username='admin', email='admin@example.invalid', password='synthetic',
                               role='platform_admin', name='Platform', organization_id=platform.id))
    db.session.commit()  # Same username/email is allowed only across organizations.
    upgrade(directory=MIGRATIONS)
    assert_current_schema()


@pytest.mark.parametrize('problem', ['duplicate', 'orphan', 'teacher_conflict', 'attachment', 'unknown_role', 'legacy_platform'])
def test_ambiguous_history_refused_before_schema_changes(migration_app, problem):
    seed_legacy()
    with db.engine.begin() as connection:
        if problem == 'duplicate':
            connection.execute(sa.text('INSERT INTO submissions(id,assignment_id,student_id) VALUES(99,8,30)'))
        elif problem == 'orphan':
            # Synthesize the legacy condition without disabling foreign keys globally.
            if connection.dialect.name == 'mysql':
                connection.execute(sa.text('SET SESSION FOREIGN_KEY_CHECKS=0'))
            connection.execute(sa.text('UPDATE assignments SET teacher_id=999 WHERE id=8'))
            if connection.dialect.name == 'mysql':
                connection.execute(sa.text('SET SESSION FOREIGN_KEY_CHECKS=1'))
        elif problem == 'teacher_conflict':
            connection.execute(sa.text('UPDATE assignments SET teacher_id=10 WHERE id=8'))
        elif problem == 'unknown_role':
            connection.execute(sa.text("UPDATE users SET role='superuser' WHERE id=10"))
        elif problem == 'legacy_platform':
            connection.execute(sa.text("UPDATE users SET role='platform_admin' WHERE id=10"))
        else:
            connection.execute(sa.text("UPDATE submissions SET file_url='/tupian/../private.txt' WHERE id=9"))
    before = set(sa.inspect(db.engine).get_table_names())
    with db.engine.connect() as connection:
        with pytest.raises(RuntimeError, match='preflight refused'):
            preflight_database(connection)
    # Flask-Migrate's public CLI helper translates a rejected RuntimeError to exit 1.
    with pytest.raises(SystemExit) as rejected:
        upgrade(directory=MIGRATIONS)
    assert rejected.value.code == 1
    assert set(sa.inspect(db.engine).get_table_names()) == before
    assert 'organizations' not in before
    with db.engine.connect() as connection:
        assert connection.execute(sa.text('SELECT COUNT(*) FROM users')).scalar_one() == 3


def synthetic_database_snapshot():
    """Compare all fixture schema and rows without exposing their contents in reports."""
    with db.engine.connect() as connection:
        inspector = sa.inspect(connection)
        snapshot = {}
        for name in sorted(inspector.get_table_names()):
            table = sa.Table(name, sa.MetaData(), autoload_with=connection)
            snapshot[name] = {
                'columns': [(c['name'], str(c['type']), c['nullable'], c.get('default'))
                            for c in inspector.get_columns(name)],
                'primary_key': inspector.get_pk_constraint(name),
                'foreign_keys': inspector.get_foreign_keys(name),
                'unique_constraints': inspector.get_unique_constraints(name),
                'indexes': inspector.get_indexes(name),
                'rows': sorted((tuple(row) for row in connection.execute(sa.select(table))), key=repr),
            }
        return snapshot


@pytest.mark.parametrize('malformed_url', [
    'http://[broken',
    'http://[not-an-ipv6]/synthetic.pdf',
    'https://example.invalid\uff0fsynthetic.pdf',
    'http://%5Bbroken',
], ids=['unclosed-ipv6', 'invalid-ipv6', 'nfkc-netloc', 'encoded-unclosed-ipv6'])
def test_malformed_attachment_aggregates_identifiers_and_refuses_without_changes(migration_app, malformed_url):
    seed_legacy(chunks=True)
    with db.engine.begin() as connection:
        # Issues before and after the malformed URL must all survive the scan.
        connection.execute(sa.text("UPDATE users SET role='unexpected-synthetic' WHERE id=20"))
        connection.execute(sa.text("UPDATE answers SET answer_image_url='file:///synthetic-answer.png' WHERE id=12"))
        connection.execute(sa.text('UPDATE submissions SET file_url=:url WHERE id=9'), {'url': malformed_url})
        connection.execute(sa.text("INSERT INTO course_resources(id,course_id,title,url) "
                                   "VALUES(15,7,'Synthetic resource','/uploads/../synthetic.pdf')"))
    before = synthetic_database_snapshot()
    expected = [
        {'type': 'invalid_user_role', 'records': [{'id': 20}]},
        {'type': 'invalid_attachment_reference', 'table': 'answers', 'id': 12, 'column': 'answer_image_url'},
        {'type': 'invalid_attachment_reference', 'table': 'submissions', 'id': 9, 'column': 'file_url'},
        {'type': 'invalid_attachment_reference', 'table': 'course_resources', 'id': 15, 'column': 'url'},
    ]
    with db.engine.connect() as connection:
        assert migration_issues(connection) == expected
        with pytest.raises(RuntimeError, match='preflight refused') as rejected:
            preflight_database(connection)
        # The report contains identifiers/reasons only, never the raw URLs.
        assert json.loads(str(rejected.value).split(': ', 1)[1]) == expected
        assert malformed_url not in str(rejected.value)
    assert synthetic_database_snapshot() == before
    with pytest.raises(SystemExit) as rejected_upgrade:
        upgrade(directory=MIGRATIONS)
    assert rejected_upgrade.value.code == 1
    assert synthetic_database_snapshot() == before


def test_offline_default_never_selects_an_organization(migration_app):
    upgrade(directory=MIGRATIONS)
    db.session.add(models.User(username='missing-org', email='missing@example.invalid',
                               password='synthetic', role='student', name='Missing'))
    with pytest.raises(sa.exc.StatementError, match='organization_id'):
        db.session.flush()
    db.session.rollback()
