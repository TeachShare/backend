"""add moderation flags

Revision ID: 8a20b61f9921
Revises: ab7ffd92053c
Create Date: 2026-05-08 10:15:12.743781

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8a20b61f9921'
down_revision = 'ab7ffd92053c'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add columns as nullable
    op.add_column('community_posts', sa.Column('is_hidden', sa.Boolean(), nullable=True))
    op.add_column('post_comments', sa.Column('is_hidden', sa.Boolean(), nullable=True))
    op.add_column('resource_collection', sa.Column('is_hidden', sa.Boolean(), nullable=True))
    op.add_column('resource_comment', sa.Column('is_hidden', sa.Boolean(), nullable=True))
    op.add_column('teachers', sa.Column('is_admin', sa.Boolean(), nullable=True))
    op.add_column('teachers', sa.Column('is_suspended', sa.Boolean(), nullable=True))

    # 2. Set default values
    op.execute("UPDATE community_posts SET is_hidden = FALSE")
    op.execute("UPDATE post_comments SET is_hidden = FALSE")
    op.execute("UPDATE resource_collection SET is_hidden = FALSE")
    op.execute("UPDATE resource_comment SET is_hidden = FALSE")
    op.execute("UPDATE teachers SET is_admin = FALSE, is_suspended = FALSE")

    # 3. Alter to NOT NULL
    op.alter_column('community_posts', 'is_hidden', nullable=False)
    op.alter_column('post_comments', 'is_hidden', nullable=False)
    op.alter_column('resource_collection', 'is_hidden', nullable=False)
    op.alter_column('resource_comment', 'is_hidden', nullable=False)
    op.alter_column('teachers', 'is_admin', nullable=False)
    op.alter_column('teachers', 'is_suspended', nullable=False)


def downgrade():
    op.drop_column('teachers', 'is_suspended')
    op.drop_column('teachers', 'is_admin')
    op.drop_column('resource_comment', 'is_hidden')
    op.drop_column('resource_collection', 'is_hidden')
    op.drop_column('post_comments', 'is_hidden')
    op.drop_column('community_posts', 'is_hidden')
