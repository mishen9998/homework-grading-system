"""Add composite indexes for role-scoped knowledge queries."""
from alembic import op
import sqlalchemy as sa


revision = 'c37a9b4102fe'
down_revision = 'b61f30d2e80a'
branch_labels = None
depends_on = None


INDEXES = {
    'ix_knowledge_entries_library_status_id': ['library', 'status', 'id'],
    'ix_knowledge_entries_library_status_created': ['library', 'status', 'created_at'],
}


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('knowledge_entries'):
        return
    existing = {item['name'] for item in inspector.get_indexes('knowledge_entries')}
    with op.batch_alter_table('knowledge_entries') as batch:
        for name, columns in INDEXES.items():
            if name not in existing:
                batch.create_index(name, columns)
    if op.get_bind().dialect.name == 'mysql' and 'ft_knowledge_entries_title_content' not in existing:
        op.execute(sa.text(
            'CREATE FULLTEXT INDEX ft_knowledge_entries_title_content '
            'ON knowledge_entries (title, content) WITH PARSER ngram'))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('knowledge_entries'):
        return
    existing = {item['name'] for item in inspector.get_indexes('knowledge_entries')}
    with op.batch_alter_table('knowledge_entries') as batch:
        if 'ft_knowledge_entries_title_content' in existing:
            batch.drop_index('ft_knowledge_entries_title_content')
        for name in INDEXES:
            if name in existing:
                batch.drop_index(name)
