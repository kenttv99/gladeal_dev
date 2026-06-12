"""split order payment expire fields

Revision ID: 9b2e7c4a6d8f
Revises: c4fd7dd4712a
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b2e7c4a6d8f"
down_revision: Union[str, Sequence[str], None] = "c4fd7dd4712a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "orders_payment_data"


def upgrade() -> None:
    op.add_column(
        TABLE_NAME,
        sa.Column("expire_payment_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("expire_payout_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(f"UPDATE {TABLE_NAME} SET expire_payment_at = expires_at")
    op.alter_column(
        TABLE_NAME,
        "expire_payment_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.drop_column(TABLE_NAME, "expires_at")


def downgrade() -> None:
    op.add_column(
        TABLE_NAME,
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        f"""
        UPDATE {TABLE_NAME}
        SET expires_at = COALESCE(expire_payment_at, expire_payout_at)
        """
    )
    op.alter_column(
        TABLE_NAME,
        "expires_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.drop_column(TABLE_NAME, "expire_payout_at")
    op.drop_column(TABLE_NAME, "expire_payment_at")
