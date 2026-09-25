"""add_payment_authorized_at_to_orders_payment_data

Revision ID: c97e1ae97a08
Revises: 150dfa04b086
Create Date: 2026-09-25 19:57:37.262117

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c97e1ae97a08'
down_revision: Union[str, Sequence[str], None] = '150dfa04b086'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('orders_payment_data', sa.Column('payment_authorized_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_orders_payment_data_payment_authorized_at', 'orders_payment_data', ['payment_authorized_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_orders_payment_data_payment_authorized_at', table_name='orders_payment_data')
    op.drop_column('orders_payment_data', 'payment_authorized_at')
