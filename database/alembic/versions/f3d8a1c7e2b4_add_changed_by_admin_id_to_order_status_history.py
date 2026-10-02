"""add_changed_by_admin_id_to_order_status_history

Revision ID: f3d8a1c7e2b4
Revises: e5a1c2d3b4f5
Create Date: 2026-10-02 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3d8a1c7e2b4'
down_revision: Union[str, Sequence[str], None] = 'e5a1c2d3b4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('order_status_history', sa.Column('changed_by_admin_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f('fk_order_status_history_changed_by_admin_id_admins'),
        'order_status_history',
        'admins',
        ['changed_by_admin_id'],
        ['id'],
    )
    op.create_index(
        op.f('ix_order_status_history_changed_by_admin_id'),
        'order_status_history',
        ['changed_by_admin_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_order_status_history_changed_by_admin_id'), table_name='order_status_history')
    op.drop_constraint(op.f('fk_order_status_history_changed_by_admin_id_admins'), 'order_status_history', type_='foreignkey')
    op.drop_column('order_status_history', 'changed_by_admin_id')
