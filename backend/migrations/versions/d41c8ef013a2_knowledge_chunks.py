"""Persist bounded knowledge passages; allow the advertised 50k CJK body.

Revision ID: d41c8ef013a2
Revises: c37a9b4102fe
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT

revision = 'd41c8ef013a2'
down_revision = 'c37a9b4102fe'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table('knowledge_chunks'):
        op.create_table('knowledge_chunks',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('entry_id', sa.Integer(), sa.ForeignKey('knowledge_entries.id', ondelete='CASCADE'), nullable=False),
            sa.Column('library', sa.String(20), nullable=False),
            sa.Column('chunk_index', sa.Integer(), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('content_hash', sa.String(64), nullable=False),
            sa.Column('embedding', sa.LargeBinary(length=64 * 1024), nullable=False),
            sa.Column('embedding_dim', sa.Integer(), nullable=False),
            sa.Column('embedding_model', sa.String(255), nullable=False),
            sa.Column('embedded_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('entry_id', 'chunk_index', name='uq_knowledge_chunk_position'))
        op.create_index('ix_knowledge_chunks_content_hash', 'knowledge_chunks', ['content_hash'])
        op.create_index('ix_knowledge_chunks_library_entry', 'knowledge_chunks', ['library', 'entry_id'])
        op.create_index('ix_knowledge_chunks_model_id', 'knowledge_chunks', ['embedding_model', 'id'])
    if bind.dialect.name == 'mysql':
        op.alter_column('knowledge_entries', 'content', existing_type=sa.Text(), type_=MEDIUMTEXT(), existing_nullable=False)


def downgrade():
    # Truncating 50k Chinese characters back to TEXT could lose data.
    raise RuntimeError('此迁移不做有损降级；回滚请切换到经过验证的备份副本')
