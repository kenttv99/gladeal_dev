"""make_user_personal_data_nullable

Revision ID: b93a283e0484
Revises: f3d8a1c7e2b4
Create Date: 2026-10-03 19:09:01.597317

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b93a283e0484'
down_revision: Union[str, Sequence[str], None] = 'f3d8a1c7e2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("users", "first_name", existing_type=sa.String(length=128), nullable=True)
    op.alter_column("users", "patronymic", existing_type=sa.String(length=128), nullable=True)
    op.alter_column("users", "last_name", existing_type=sa.String(length=128), nullable=True)
    op.alter_column("users", "birth_date", existing_type=sa.DateTime(timezone=True), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("users", "birth_date", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("users", "last_name", existing_type=sa.String(length=128), nullable=False)
    op.alter_column("users", "patronymic", existing_type=sa.String(length=128), nullable=False)
    op.alter_column("users", "first_name", existing_type=sa.String(length=128), nullable=False)

