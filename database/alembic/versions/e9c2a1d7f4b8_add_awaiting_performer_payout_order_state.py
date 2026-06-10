"""add awaiting performer payout order state

Revision ID: e9c2a1d7f4b8
Revises: b8a7f2d4c1e9
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "e9c2a1d7f4b8"
down_revision: Union[str, Sequence[str], None] = "b8a7f2d4c1e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_ORDER_STATES = (
    "awaiting_performer",
    "awaiting_payment",
    "awaiting_performer_confirmation",
    "awaiting_client_confirmation",
    "awaiting_conflict",
    "open_conflict",
    "successful_completion",
    "unsuccessful_completion",
    "cancled_by_expire_time_to_client",
    "confirm_by_expire_time_to_performer",
    "closed_by_arbiter_to_client",
    "closed_by_arbiter_to_performer",
)
NEW_ORDER_STATES = (
    *OLD_ORDER_STATES[:4],
    "awaiting_performer_payout",
    *OLD_ORDER_STATES[4:],
)
ORDER_STATE_CONSTRAINTS = (
    ("orders", "status", "ck_orders_order_states"),
    ("order_status_history", "old_status", "ck_order_status_history_order_history_old_states"),
    ("order_status_history", "new_status", "ck_order_status_history_order_history_new_states"),
)


def _states_sql(states: tuple[str, ...]) -> str:
    return ", ".join(f"'{state}'" for state in states)


def _replace_constraints(states: tuple[str, ...]) -> None:
    for table, column, constraint in ORDER_STATE_CONSTRAINTS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {constraint} "
            f"CHECK ({column} IN ({_states_sql(states)}))"
        )


def upgrade() -> None:
    _replace_constraints(NEW_ORDER_STATES)


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM orders WHERE status = 'awaiting_performer_payout'
                UNION ALL
                SELECT 1 FROM order_status_history WHERE old_status = 'awaiting_performer_payout'
                UNION ALL
                SELECT 1 FROM order_status_history WHERE new_status = 'awaiting_performer_payout'
            ) THEN
                RAISE EXCEPTION 'Cannot downgrade: awaiting_performer_payout is present in order data';
            END IF;
        END $$
        """
    )
    _replace_constraints(OLD_ORDER_STATES)
