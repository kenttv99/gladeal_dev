from __future__ import annotations

import argparse
import asyncio
import sys
from getpass import getpass
from pathlib import Path

from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.enums.enums_v1 import AdminRoles
from api.utils.admin_password_methods import (
    hash_admin_password,
    read_admin_password_hash,
    verify_admin_password_hash,
)
from database.config import AsyncSessionLocal
from database.models.users import Admin


def _prompt(name: str, *, secret: bool = False) -> str:
    value = (getpass if secret else input)(f"{name}: ").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _parse_role(value: str) -> AdminRoles:
    try:
        return AdminRoles(value.strip().lower())
    except ValueError as exc:
        options = ", ".join(role.value for role in AdminRoles)
        raise ValueError(f"role must be one of: {options}") from exc


async def create_admin(first_name: str, last_name: str, email: str, role: str, password: str) -> int:
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


async def main() -> None:
    parser = argparse.ArgumentParser(description="Create admin user")
    parser.add_argument("--first-name")
    parser.add_argument("--last-name")
    parser.add_argument("--email")
    parser.add_argument("--role")
    parser.add_argument("--password")
    parser.add_argument("--confirm-password")
    args = parser.parse_args()

    first_name = args.first_name or _prompt("first_name")
    last_name = args.last_name or _prompt("last_name")
    email = args.email or _prompt("email")
    role = args.role or _prompt(f"role ({', '.join(role.value for role in AdminRoles)})")
    password = args.password or _prompt("password", secret=True)
    password_confirm = args.confirm_password or _prompt("confirm_password", secret=True)
    if password != password_confirm:
        raise ValueError("password confirmation does not match")

    admin_id = await create_admin(first_name, last_name, email, role, password)
    print(f"admin_created id={admin_id} email={email} role={_parse_role(role).value}")


if __name__ == "__main__":
    asyncio.run(main())
