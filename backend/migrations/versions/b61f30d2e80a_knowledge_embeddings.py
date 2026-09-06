"""Persist local semantic vectors for approved knowledge entries."""
from alembic import op
import sqlalchemy as sa

revision = 'b61f30d2e80a'
down_revision = 'a92c61e803bd'
branch_labels = None
depends_on = None


def upgrade():
    columns = {item['name'] for item in sa.inspect(op.get_bind()).get_columns('knowledge_entries')}
    with op.batch_alter_table('knowledge_entries') as batch:
        if 'embedding' not in columns:
            batch.add_column(sa.Column('embedding', sa.LargeBinary(length=64 * 1024)))
        if 'embedding_dim' not in columns:
            batch.add_column(sa.Column('embedding_dim', sa.Integer()))
        if 'embedding_model' not in columns:
            batch.add_column(sa.Column('embedding_model', sa.String(255)))
        if 'embedding_hash' not in columns:
            batch.add_column(sa.Column('embedding_hash', sa.String(64)))
            batch.create_index('ix_knowledge_entries_embedding_hash', ['embedding_hash'])
        if 'embedded_at' not in columns:
            batch.add_column(sa.Column('embedded_at', sa.DateTime()))


def downgrade():
    with op.batch_alter_table('knowledge_entries') as batch:
        batch.drop_index('ix_knowledge_entries_embedding_hash')
        for name in ('embedded_at', 'embedding_hash', 'embedding_model', 'embedding_dim', 'embedding'):
            batch.drop_column(name)
