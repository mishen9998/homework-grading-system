"""Create role-separated knowledge entries and private attachments."""
from alembic import op
import sqlalchemy as sa

revision = 'a92c61e803bd'
down_revision = 'fde30f938654'
branch_labels = None
depends_on = None


def upgrade():
    # Development installations may already have the table from create_all.
    if sa.inspect(op.get_bind()).has_table('knowledge_entries'):
        return
    op.create_table('knowledge_entries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('library', sa.String(20), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('source_url', sa.String(1000), nullable=False),
        sa.Column('author_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('review_note', sa.String(1000), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('reviewed_at', sa.DateTime()),
        sa.Column('filename', sa.String(255)),
        sa.Column('attachment', sa.LargeBinary(length=5 * 1024 * 1024)))
    op.create_index('ix_knowledge_entries_library', 'knowledge_entries', ['library'])
    op.create_index('ix_knowledge_entries_status', 'knowledge_entries', ['status'])


def downgrade():
    op.drop_table('knowledge_entries')
