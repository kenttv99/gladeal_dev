"""allow empty performer payment email

Revision ID: f6a2b7c9d4e1
Revises: e9c2a1d7f4b8
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a2b7c9d4e1"
down_revision: Union[str, Sequence[str], None] = "e9c2a1d7f4b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "orders_payment_data",
        "performer_email",
        existing_type=sa.String(length=100),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "orders_payment_data",
        "performer_email",
        existing_type=sa.String(length=100),
        nullable=False,
    )
