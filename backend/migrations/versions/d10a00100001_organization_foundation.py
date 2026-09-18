"""Versioned organization foundation; preserve legacy IDs and reject ambiguity."""
from datetime import datetime
from alembic import op
import sqlalchemy as sa
from migrations.schema_support import BUSINESS_TABLES, legacy_metadata, preflight_database

revision = 'd10a00100001'
down_revision = 'c37a9b4102fe'
branch_labels = None
depends_on = None


def _columns(connection, table):
    return {c['name'] for c in sa.inspect(connection).get_columns(table)}


def upgrade():
    connection = op.get_bind()
    preflight_database(connection)
    tables = set(sa.inspect(connection).get_table_names())
    if 'organizations' not in tables:
        op.create_table('organizations',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('code', sa.String(80), nullable=False),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('expires_at', sa.DateTime()),
            sa.Column('user_limit', sa.Integer(), nullable=False),
            sa.Column('storage_limit_bytes', sa.BigInteger(), nullable=False),
            sa.Column('ai_monthly_token_limit', sa.BigInteger(), nullable=False),
            sa.Column('concurrent_task_limit', sa.Integer(), nullable=False),
            sa.Column('ai_enabled', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('code', name='uq_organization_code'),
            sa.CheckConstraint("status IN ('active', 'disabled')", name='ck_organization_status'),
            sa.CheckConstraint('user_limit >= 0 AND storage_limit_bytes >= 0 AND '
                               'ai_monthly_token_limit >= 0 AND concurrent_task_limit >= 0',
                               name='ck_organization_limits'))
    orgs = sa.Table('organizations', sa.MetaData(), autoload_with=connection)
    for code, name in (('default', '历史默认机构'), ('platform', '平台管理')):
        if connection.execute(sa.select(orgs.c.id).where(orgs.c.code == code)).scalar() is None:
            connection.execute(orgs.insert().values(code=code, name=name, status='active',
                expires_at=None, user_limit=500, storage_limit_bytes=1073741824,
                ai_monthly_token_limit=100000, concurrent_task_limit=2, ai_enabled=False,
                created_at=datetime.utcnow(), updated_at=datetime.utcnow()))
    default_id = connection.execute(sa.select(orgs.c.id).where(orgs.c.code == 'default')).scalar_one()
    if 'organization_classes' not in tables:
        op.create_table('organization_classes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('organization_id', 'name', name='uq_organization_class_name'))
        op.create_index('ix_organization_classes_organization_id', 'organization_classes', ['organization_id'])
    if 'knowledge_chunks' not in tables:
        legacy_metadata(include_knowledge=True, include_chunks=True).tables['knowledge_chunks'].create(connection)
    for table in BUSINESS_TABLES:
        if 'organization_id' not in _columns(connection, table):
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        connection.execute(sa.text(f'UPDATE {table} SET organization_id=:organization_id '
                                   'WHERE organization_id IS NULL'), {'organization_id': default_id})
        inspector = sa.inspect(connection)
        columns = {c['name']: c for c in inspector.get_columns(table)}
        foreign_keys = inspector.get_foreign_keys(table)
        indexes = {i['name'] for i in inspector.get_indexes(table)}
        with op.batch_alter_table(table) as batch:
            if columns['organization_id']['nullable']:
                batch.alter_column('organization_id', existing_type=sa.Integer(), nullable=False)
            if not any(f['constrained_columns'] == ['organization_id'] for f in foreign_keys):
                batch.create_foreign_key(f'fk_{table}_organization', 'organizations', ['organization_id'], ['id'])
            if f'ix_{table}_organization_id' not in indexes:
                batch.create_index(f'ix_{table}_organization_id', ['organization_id'])
    user_columns = _columns(connection, 'users')
    with op.batch_alter_table('users') as batch:
        if 'is_active' not in user_columns:
            batch.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
        if 'token_version' not in user_columns:
            batch.add_column(sa.Column('token_version', sa.Integer(), nullable=False, server_default='1'))
        if 'organization_class_id' not in user_columns:
            batch.add_column(sa.Column('organization_class_id', sa.Integer()))
            batch.create_foreign_key('fk_users_organization_class', 'organization_classes',
                                     ['organization_class_id'], ['id'])
    unique_constraints = sa.inspect(connection).get_unique_constraints('users')
    with op.batch_alter_table('users', naming_convention={'uq': 'uq_%(table_name)s_%(column_0_name)s'}) as batch:
        for constraint in unique_constraints:
            if constraint['column_names'] in (['username'], ['email']):
                batch.drop_constraint(constraint['name'] or f"uq_users_{constraint['column_names'][0]}", type_='unique')
        existing_unique = {tuple(u['column_names']) for u in unique_constraints}
        if ('organization_id', 'username') not in existing_unique:
            batch.create_unique_constraint('uq_user_organization_username', ['organization_id', 'username'])
        if ('organization_id', 'email') not in existing_unique:
            batch.create_unique_constraint('uq_user_organization_email', ['organization_id', 'email'])
    classes = sa.Table('organization_classes', sa.MetaData(), autoload_with=connection)
    for source in ('users', 'courses', 'schedules'):
        rows = connection.execute(sa.text(f'SELECT DISTINCT organization_id, class_name FROM {source} '
                                          "WHERE class_name IS NOT NULL AND class_name != ''")).mappings()
        for row in rows:
            existing = connection.execute(sa.select(classes.c.id).where(
                classes.c.organization_id == row['organization_id'], classes.c.name == row['class_name'])).scalar()
            if existing is None:
                connection.execute(classes.insert().values(organization_id=row['organization_id'],
                    name=row['class_name'], created_at=datetime.utcnow()))
    for row in connection.execute(sa.select(classes)).mappings().all():
        connection.execute(sa.text('UPDATE users SET organization_class_id=:class_id '
            'WHERE organization_id=:organization_id AND class_name=:class_name '
            'AND organization_class_id IS NULL'), {'class_id': row['id'],
            'organization_id': row['organization_id'], 'class_name': row['name']})
    if 'audit_logs' not in tables:
        op.create_table('audit_logs', sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id')),
            sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id')),
            sa.Column('action', sa.String(100), nullable=False),
            sa.Column('target_type', sa.String(80)), sa.Column('target_id', sa.String(100)),
            sa.Column('details', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False))
        op.create_index('ix_audit_organization_created', 'audit_logs', ['organization_id', 'created_at'])


def downgrade():
    raise RuntimeError('Organization migration cannot be downgraded without losing ownership. '
                       'Restore the verified pre-upgrade database and attachment backup instead.')
