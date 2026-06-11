"""split order payment statuses

Revision ID: c4fd7dd4712a
Revises: d7e4f9a1c2b3
Create Date: 2026-06-11 17:54:15.695871

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4fd7dd4712a"
down_revision: Union[str, Sequence[str], None] = "d7e4f9a1c2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "orders_payment_data"
ORDER_PAYMENT_STATES = (
    "registered",
    "authorized",
    "completed",
    "blocked",
    "canceled",
    "expired",
)
OLD_STATUS_CONSTRAINT = "ck_orders_payment_data_order_payment_states"
STATUS_CONSTRAINTS = {
    "payment_status": "ck_orders_payment_data_order_payment_status_states",
    "payout_status": "ck_orders_payment_data_order_payout_status_states",
    "revoke_status": "ck_orders_payment_data_order_revoke_status_states",
}


def _states_sql() -> str:
    return ", ".join(f"'{state}'" for state in ORDER_PAYMENT_STATES)


def _drop_constraint(name: str) -> None:
    op.execute(f"ALTER TABLE {TABLE_NAME} DROP CONSTRAINT IF EXISTS {name}")


def _create_status_constraint(column: str, name: str, nullable: bool) -> None:
    null_check = f"{column} IS NULL OR " if nullable else ""
    op.execute(
        f"ALTER TABLE {TABLE_NAME} ADD CONSTRAINT {name} "
        f"CHECK ({null_check}{column} IN ({_states_sql()}))"
    )


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_orders_payment_data_status")
    _drop_constraint(OLD_STATUS_CONSTRAINT)

    op.add_column(TABLE_NAME, sa.Column("payment_status", sa.String(length=20), nullable=True))
    op.add_column(TABLE_NAME, sa.Column("payout_status", sa.String(length=20), nullable=True))
    op.add_column(TABLE_NAME, sa.Column("revoke_status", sa.String(length=20), nullable=True))

    op.execute(
        f"""
        UPDATE {TABLE_NAME}
        SET
            payment_status = CASE
                WHEN paygine_payout_operation_id IS NOT NULL THEN 'completed'
                ELSE status
            END,
            payout_status = CASE
                WHEN paygine_payout_operation_id IS NULL THEN NULL
                WHEN status = 'completed' THEN 'completed'
                ELSE 'registered'
            END,
            revoke_status = CASE
                WHEN status IN ('blocked', 'canceled') THEN status
                ELSE NULL
            END
        """
    )
    op.alter_column(
        TABLE_NAME,
        "payment_status",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default="registered",
    )

    op.alter_column(
        TABLE_NAME,
        "paygine_refund_operation_id",
        new_column_name="paygine_revoked_operation_id",
        existing_type=sa.String(length=64),
        existing_nullable=True,
    )
    op.alter_column(
        TABLE_NAME,
        "refunded_at",
        new_column_name="payment_complete_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )

    for column, constraint in STATUS_CONSTRAINTS.items():
        _create_status_constraint(column, constraint, nullable=column != "payment_status")

    op.create_index(
        "ix_orders_payment_data_payment_status",
        TABLE_NAME,
        ["payment_status"],
        unique=False,
    )
    op.create_index(
        "ix_orders_payment_data_payout_status",
        TABLE_NAME,
        ["payout_status"],
        unique=False,
    )
    op.create_index(
        "ix_orders_payment_data_revoke_status",
        TABLE_NAME,
        ["revoke_status"],
        unique=False,
    )
    op.drop_column(TABLE_NAME, "status")


def downgrade() -> None:
    op.add_column(
        TABLE_NAME,
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="registered",
            nullable=True,
        ),
    )
    op.execute(
        f"""
        UPDATE {TABLE_NAME}
        SET status = COALESCE(revoke_status, payout_status, payment_status)
        """
    )
    op.alter_column(
        TABLE_NAME,
        "status",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default="registered",
    )

    op.drop_index("ix_orders_payment_data_revoke_status", table_name=TABLE_NAME)
    op.drop_index("ix_orders_payment_data_payout_status", table_name=TABLE_NAME)
    op.drop_index("ix_orders_payment_data_payment_status", table_name=TABLE_NAME)
    for constraint in STATUS_CONSTRAINTS.values():
        _drop_constraint(constraint)

    _create_status_constraint("status", OLD_STATUS_CONSTRAINT, nullable=False)
    op.create_index("ix_orders_payment_data_status", TABLE_NAME, ["status"], unique=False)

    op.alter_column(
        TABLE_NAME,
        "payment_complete_at",
        new_column_name="refunded_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        TABLE_NAME,
        "paygine_revoked_operation_id",
        new_column_name="paygine_refund_operation_id",
        existing_type=sa.String(length=64),
        existing_nullable=True,
    )
    op.drop_column(TABLE_NAME, "revoke_status")
    op.drop_column(TABLE_NAME, "payout_status")
    op.drop_column(TABLE_NAME, "payment_status")
