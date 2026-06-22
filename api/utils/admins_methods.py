from __future__ import annotations

from sqlalchemy import update, insert
from sqlalchemy.exc import IntegrityError

from api.utils.admin_password_methods import (
    hash_admin_password,
    read_admin_password_hash,
    verify_admin_password_hash,
)
from database.config import AsyncSessionLocal
from database.models.users import Admin
from api.enums.enums_v1 import AdminRoles


def _parse_role(value: str) -> AdminRoles:
    try:
        return AdminRoles(value.strip().lower())
    except ValueError as exc:
        options = ", ".join(role.value for role in AdminRoles)
        raise ValueError(f"role must be one of: {options}") from exc


async def create_admin(first_name: str, last_name: str, email: str, role: str, password: str) -> int:
    '''Создаем админа с нужной ролью'''
    role_value = _parse_role(role)
    password_hash = hash_admin_password(password)
    read_admin_password_hash(password_hash)
    if not verify_admin_password_hash(password, password_hash):
        raise RuntimeError("Password hash verification failed")

    async with AsyncSessionLocal() as session:
        try:
            async with session.begin():
                result = await session.execute(
                    insert(Admin)
                    .values(
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        role=role_value,
                        password_hash=password_hash,
                    )
                    .returning(Admin.id)
                )
                return result.scalar_one()
        except IntegrityError as exc:
            if "uq_admins_email" in str(exc.orig):
                raise ValueError("Admin with this email already exists") from exc
            raise

async def change_admin_password_by_email(email: str, password: str) -> int:
    '''Меняем пароль у сущесвтующего админа'''
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
