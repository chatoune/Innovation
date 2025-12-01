"""Create users table

Revision ID: 002
Revises: 001
Create Date: 2025-12-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('failed_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create unique index on email
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # Add foreign key constraint to audit_logs.user_id
    op.create_foreign_key(
        'fk_audit_logs_user_id',
        'audit_logs',
        'users',
        ['user_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    # Remove foreign key constraint
    op.drop_constraint('fk_audit_logs_user_id', 'audit_logs', type_='foreignkey')

    # Drop index and table
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
