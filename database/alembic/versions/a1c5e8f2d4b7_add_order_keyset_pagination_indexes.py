"""add order keyset pagination indexes

Revision ID: a1c5e8f2d4b7
Revises: e3f8a2b9c4d1
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "a1c5e8f2d4b7"
down_revision: Union[str, Sequence[str], None] = "e3f8a2b9c4d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_orders_client_created_id", "orders", ["client_id", "created_at", "id"])
    op.create_index(
        "ix_orders_performer_created_id",
        "orders",
        ["performer_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_orders_performer_created_id", table_name="orders")
    op.drop_index("ix_orders_client_created_id", table_name="orders")
