"""add_two_factor_fields

Revision ID: 3101d2009ab8
Revises: c97e1ae97a08
Create Date: 2026-09-27 19:20:02.616721

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3101d2009ab8'
down_revision: Union[str, Sequence[str], None] = 'c97e1ae97a08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('admins', sa.Column('two_factor_secret', sa.String(length=32), nullable=True))
    op.add_column('admins', sa.Column('is_two_factor_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('admins', sa.Column('two_factor_backup_codes', sa.JSON(), nullable=True))
    op.add_column('users', sa.Column('two_factor_secret', sa.String(length=32), nullable=True))
    op.add_column('users', sa.Column('is_two_factor_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('users', sa.Column('two_factor_backup_codes', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'two_factor_backup_codes')
    op.drop_column('users', 'is_two_factor_enabled')
    op.drop_column('users', 'two_factor_secret')
    op.drop_column('admins', 'two_factor_backup_codes')
    op.drop_column('admins', 'is_two_factor_enabled')
    op.drop_column('admins', 'two_factor_secret')
