"""add awaiting client payout order state

Revision ID: c8d4e9f1a2b3
Revises: a1c5e8f2d4b7
Create Date: 2026-06-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c8d4e9f1a2b3"
down_revision: Union[str, Sequence[str], None] = "a1c5e8f2d4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_ORDER_STATES = (
    "awaiting_performer",
    "awaiting_payment",
    "awaiting_performer_confirmation",
    "awaiting_client_confirmation",
    "awaiting_performer_payout",
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
    *OLD_ORDER_STATES[:5],
    "awaiting_client_payout",
    *OLD_ORDER_STATES[5:],
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
                SELECT 1 FROM orders WHERE status = 'awaiting_client_payout'
                UNION ALL
                SELECT 1 FROM order_status_history WHERE old_status = 'awaiting_client_payout'
                UNION ALL
                SELECT 1 FROM order_status_history WHERE new_status = 'awaiting_client_payout'
            ) THEN
                RAISE EXCEPTION 'Cannot downgrade: awaiting_client_payout is present in order data';
            END IF;
        END $$;
        """
    )
    _replace_constraints(OLD_ORDER_STATES)
