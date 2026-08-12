"""add_request_logs

Revision ID: a1b2c3d4e5f6
Revises: 99c9d2fcb883
Create Date: 2026-08-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '99c9d2fcb883'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('request_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('method', sa.String(length=10), nullable=False),
    sa.Column('path', sa.String(length=255), nullable=False),
    sa.Column('status_code', sa.Integer(), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_reqlog_user_created', 'request_logs', ['user_id', 'created_at'], unique=False)
    op.create_index('idx_reqlog_path', 'request_logs', ['path'], unique=False)
    op.create_index('idx_reqlog_status', 'request_logs', ['status_code'], unique=False)
    op.create_index('idx_reqlog_created', 'request_logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_reqlog_created', table_name='request_logs')
    op.drop_index('idx_reqlog_status', table_name='request_logs')
    op.drop_index('idx_reqlog_path', table_name='request_logs')
    op.drop_index('idx_reqlog_user_created', table_name='request_logs')
    op.drop_table('request_logs')