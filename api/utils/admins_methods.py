from __future__ import annotations

from sqlalchemy import update

from api.utils.admin_password_methods import hash_admin_password
from database.config import AsyncSessionLocal
from database.models.users import Admin


async def change_admin_password_by_email(email: str, password: str) -> int:
    password_hash = hash_admin_password(password)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                update(Admin)
                .where(Admin.email == email)
                .values(password_hash=password_hash)
                .returning(Admin.id)
            )
            admin_id = result.scalar_one_or_none()
            if admin_id is None:
                raise ValueError("Admin with this email does not exist")
            return admin_id
