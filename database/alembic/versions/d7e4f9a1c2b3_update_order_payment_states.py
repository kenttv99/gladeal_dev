"""update order payment states

Revision ID: d7e4f9a1c2b3
Revises: 3156bde2c77b
Create Date: 2026-06-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "d7e4f9a1c2b3"
down_revision: Union[str, Sequence[str], None] = "3156bde2c77b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ORDER_PAYMENT_STATE_CONSTRAINT = "ck_orders_payment_data_order_payment_states"
OLD_ORDER_PAYMENT_STATES = (
    "created",
    "payment_link_created",
    "funds_frozen",
    "payout_link_created",
    "payout_completed",
    "refunded",
    "revoked",
    "failed",
)
NEW_ORDER_PAYMENT_STATES = (
    "registered",
    "authorized",
    "completed",
    "blocked",
    "canceled",
    "expired",
)
UPGRADE_STATE_MAP = {
    "created": "registered",
    "payment_link_created": "registered",
    "funds_frozen": "authorized",
    "payout_link_created": "authorized",
    "payout_completed": "completed",
    "refunded": "blocked",
    "revoked": "canceled",
    "failed": "canceled",
}
DOWNGRADE_STATE_MAP = {
    "registered": "created",
    "authorized": "funds_frozen",
    "completed": "payout_completed",
    "blocked": "refunded",
    "canceled": "revoked",
    "expired": "failed",
}


def _states_sql(states: tuple[str, ...]) -> str:
    return ", ".join(f"'{state}'" for state in states)


def _case_sql(state_map: dict[str, str]) -> str:
    return "\n".join(
        f"            WHEN '{old_state}' THEN '{new_state}'"
        for old_state, new_state in state_map.items()
    )


def _drop_state_constraint() -> None:
    op.execute(
        f"ALTER TABLE orders_payment_data DROP CONSTRAINT IF EXISTS {ORDER_PAYMENT_STATE_CONSTRAINT}"
    )


def _create_state_constraint(states: tuple[str, ...]) -> None:
    op.execute(
        f"ALTER TABLE orders_payment_data ADD CONSTRAINT {ORDER_PAYMENT_STATE_CONSTRAINT} "
        f"CHECK (status IN ({_states_sql(states)}))"
    )


def _remap_states(state_map: dict[str, str]) -> None:
    op.execute(
        f"""
        UPDATE orders_payment_data
        SET status = CASE status
{_case_sql(state_map)}
            ELSE status
        END
        WHERE status IN ({_states_sql(tuple(state_map))})
        """
    )


def upgrade() -> None:
    _drop_state_constraint()
    op.execute("ALTER TABLE orders_payment_data ALTER COLUMN status SET DEFAULT 'registered'")
    _remap_states(UPGRADE_STATE_MAP)
    _create_state_constraint(NEW_ORDER_PAYMENT_STATES)


def downgrade() -> None:
    _drop_state_constraint()
    op.execute("ALTER TABLE orders_payment_data ALTER COLUMN status SET DEFAULT 'created'")
    _remap_states(DOWNGRADE_STATE_MAP)
    _create_state_constraint(OLD_ORDER_PAYMENT_STATES)
