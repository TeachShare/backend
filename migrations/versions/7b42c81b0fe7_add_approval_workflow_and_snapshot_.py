"""add_approval_workflow_and_snapshot_fields

Revision ID: 7b42c81b0fe7
Revises: 9c15d2ce3787
Create Date: 2026-05-15 02:09:53.660711

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '7b42c81b0fe7'
down_revision = '9c15d2ce3787'
branch_labels = None
depends_on = None


def upgrade():
    # Fix resource_collection.description type change with explicit cast
    op.execute('ALTER TABLE resource_collection ALTER COLUMN description TYPE JSONB USING description::jsonb')
    
    with op.batch_alter_table('resource_collection', schema=None) as batch_op:
        batch_op.alter_column('subject_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('grade_level_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('content_type_id',
               existing_type=sa.INTEGER(),
               nullable=True)

    with op.batch_alter_table('resource_version', schema=None) as batch_op:
        batch_op.add_column(sa.Column('title', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('description', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
        batch_op.add_column(sa.Column('is_approved', sa.Boolean(), server_default='true', nullable=False))
        batch_op.add_column(sa.Column('approved_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_resource_version_approved_by', 'teachers', ['approved_by'], ['teacher_id'])


def downgrade():
    with op.batch_alter_table('resource_version', schema=None) as batch_op:
        batch_op.drop_constraint('fk_resource_version_approved_by', type_='foreignkey')
        batch_op.drop_column('approved_by')
        batch_op.drop_column('is_approved')
        batch_op.drop_column('description')
        batch_op.drop_column('title')

    with op.batch_alter_table('resource_collection', schema=None) as batch_op:
        batch_op.alter_column('content_type_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('grade_level_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('subject_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        
    op.execute('ALTER TABLE resource_collection ALTER COLUMN description TYPE TEXT USING description::text')
