"""add admin tables

Revision ID: b6d2a4c9f1e8
Revises: 9b2e7c4a6d8f
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b6d2a4c9f1e8"
down_revision: Union[str, Sequence[str], None] = "9b2e7c4a6d8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "admins",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column("last_name", sa.String(length=128), nullable=False),
        sa.Column("phone_number", sa.String(length=32), nullable=False),
        sa.Column(
            "role",
            sa.Enum("superuser", "admin", "support", name="admin_roles", native_enum=False, create_constraint=True),
            server_default="admin",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admins")),
        sa.UniqueConstraint("phone_number", name=op.f("uq_admins_phone_number")),
    )
    op.create_table(
        "admin_refresh_tokens",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("admin_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["admin_id"],
            ["admins.id"],
            name=op.f("fk_admin_refresh_tokens_admin_id_admins"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_admin_refresh_tokens_token_hash")),
    )
    op.create_index(
        op.f("ix_admin_refresh_tokens_admin_id"),
        "admin_refresh_tokens",
        ["admin_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_admin_refresh_tokens_admin_id"), table_name="admin_refresh_tokens")
    op.drop_table("admin_refresh_tokens")
    op.drop_table("admins")
