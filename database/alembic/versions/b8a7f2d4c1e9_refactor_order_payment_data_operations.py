"""refactor order payment data operations

Revision ID: b8a7f2d4c1e9
Revises: a43c9f0f4d12
Create Date: 2026-06-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8a7f2d4c1e9"
down_revision: Union[str, Sequence[str], None] = "a43c9f0f4d12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_orders_payment_data_paygine_order_id", table_name="orders_payment_data")
    op.execute(
        """
        UPDATE orders_payment_data
        SET paygine_payment_operation_id = paygine_order_id
        """
    )
    op.alter_column(
        "orders_payment_data",
        "paygine_payment_operation_id",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.drop_column("orders_payment_data", "paygine_order_id")
    op.drop_column("orders_payment_data", "customer_payment_amount")
    op.drop_column("orders_payment_data", "performer_payout_amount")
    op.create_index(
        "ix_orders_payment_data_paygine_payment_operation_id",
        "orders_payment_data",
        ["paygine_payment_operation_id"],
        unique=True,
    )
    op.create_index(
        "ix_orders_payment_data_paygine_payout_operation_id",
        "orders_payment_data",
        ["paygine_payout_operation_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_orders_payment_data_paygine_payout_operation_id",
        table_name="orders_payment_data",
    )
    op.drop_index(
        "ix_orders_payment_data_paygine_payment_operation_id",
        table_name="orders_payment_data",
    )
    op.add_column(
        "orders_payment_data",
        sa.Column(
            "performer_payout_amount",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
    )
    op.add_column(
        "orders_payment_data",
        sa.Column(
            "customer_payment_amount",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
    )
    op.add_column(
        "orders_payment_data",
        sa.Column("paygine_order_id", sa.String(length=64), nullable=True),
    )
    op.execute(
        """
        UPDATE orders_payment_data
        SET
            paygine_order_id = paygine_payment_operation_id,
            customer_payment_amount = order_amount + service_fee_amount,
            performer_payout_amount = order_amount
        """
    )
    op.alter_column(
        "orders_payment_data",
        "paygine_order_id",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        "orders_payment_data",
        "customer_payment_amount",
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=False,
    )
    op.alter_column(
        "orders_payment_data",
        "performer_payout_amount",
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=False,
    )
    op.alter_column(
        "orders_payment_data",
        "paygine_payment_operation_id",
        existing_type=sa.String(length=64),
        nullable=True,
    )
    op.create_index(
        "ix_orders_payment_data_paygine_order_id",
        "orders_payment_data",
        ["paygine_order_id"],
        unique=True,
    )
