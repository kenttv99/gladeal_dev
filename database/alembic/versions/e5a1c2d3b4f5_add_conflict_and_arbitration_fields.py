"""add_conflict_and_arbitration_fields

Revision ID: e5a1c2d3b4f5
Revises: 3101d2009ab8
Create Date: 2026-10-01 14:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a1c2d3b4f5'
down_revision: Union[str, Sequence[str], None] = '3101d2009ab8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('orders', sa.Column('performer_connected_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('client_declined_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('arbitration_reason', sa.Text(), nullable=True))
    op.create_index('ix_orders_performer_connected_at', 'orders', ['performer_connected_at'], unique=False)
    op.create_index('ix_orders_client_declined_at', 'orders', ['client_declined_at'], unique=False)

    op.add_column('order_status_history', sa.Column('comment', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('order_status_history', 'comment')

    op.drop_index('ix_orders_client_declined_at', table_name='orders')
    op.drop_index('ix_orders_performer_connected_at', table_name='orders')
    op.drop_column('orders', 'arbitration_reason')
    op.drop_column('orders', 'client_declined_at')
    op.drop_column('orders', 'performer_connected_at')
