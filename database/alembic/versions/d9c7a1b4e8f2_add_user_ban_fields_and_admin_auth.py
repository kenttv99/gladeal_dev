"""add user ban fields and admin auth fields

Revision ID: d9c7a1b4e8f2
Revises: b6d2a4c9f1e8
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d9c7a1b4e8f2"
down_revision: Union[str, Sequence[str], None] = "b6d2a4c9f1e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("is_banned", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("ban_reason", sa.String(), nullable=True))
    op.add_column("users", sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True))

    op.drop_constraint(op.f("uq_admins_phone_number"), "admins", type_="unique")
    op.alter_column(
        "admins",
        "phone_number",
        new_column_name="email",
        existing_type=sa.String(length=32),
        existing_nullable=False,
    )
    op.add_column("admins", sa.Column("password_hash", sa.String(length=256), nullable=False))
    op.create_unique_constraint(op.f("uq_admins_email"), "admins", ["email"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("uq_admins_email"), "admins", type_="unique")
    op.drop_column("admins", "password_hash")
    op.alter_column(
        "admins",
        "email",
        new_column_name="phone_number",
        existing_type=sa.String(length=32),
        existing_nullable=False,
    )
    op.create_unique_constraint(op.f("uq_admins_phone_number"), "admins", ["phone_number"])

    op.drop_column("users", "banned_at")
    op.drop_column("users", "ban_reason")
    op.drop_column("users", "is_banned")
