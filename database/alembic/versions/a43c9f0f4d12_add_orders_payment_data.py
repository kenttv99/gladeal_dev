"""add orders payment data

Revision ID: a43c9f0f4d12
Revises: f2b4a6d9c1e3
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a43c9f0f4d12"
down_revision: Union[str, Sequence[str], None] = "f2b4a6d9c1e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ORDER_PAYMENT_STATES = (
    "created",
    "payment_link_created",
    "funds_frozen",
    "payout_link_created",
    "payout_completed",
    "refunded",
    "revoked",
    "failed",
)


def upgrade() -> None:
    op.create_table(
        "orders_payment_data",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_email", sa.String(length=100), nullable=False),
        sa.Column("performer_email", sa.String(length=100), nullable=False),
        sa.Column("currency", sa.Integer(), server_default="643", nullable=False),
        sa.Column("order_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("service_fee_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("customer_payment_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("performer_payout_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                *ORDER_PAYMENT_STATES,
                name="order_payment_states",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="created",
            nullable=False,
        ),
        sa.Column("paygine_order_id", sa.String(length=64), nullable=False),
        sa.Column("paygine_payment_operation_id", sa.String(length=64), nullable=True),
        sa.Column("paygine_payout_operation_id", sa.String(length=64), nullable=True),
        sa.Column("paygine_refund_operation_id", sa.String(length=64), nullable=True),
        sa.Column("customer_payment_url", sa.String(length=500), nullable=True),
        sa.Column("performer_payout_url", sa.String(length=500), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("funds_frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payout_link_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payout_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_orders_payment_data_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders_payment_data")),
    )
    op.create_index(
        "ix_orders_payment_data_order_id",
        "orders_payment_data",
        ["order_id"],
        unique=True,
    )
    op.create_index(
        "ix_orders_payment_data_paygine_order_id",
        "orders_payment_data",
        ["paygine_order_id"],
        unique=True,
    )
    op.create_index(
        "ix_orders_payment_data_status",
        "orders_payment_data",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_orders_payment_data_status", table_name="orders_payment_data")
    op.drop_index("ix_orders_payment_data_paygine_order_id", table_name="orders_payment_data")
    op.drop_index("ix_orders_payment_data_order_id", table_name="orders_payment_data")
    op.drop_table("orders_payment_data")
