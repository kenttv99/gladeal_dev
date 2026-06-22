from __future__ import annotations

import argparse
import asyncio
import sys
from getpass import getpass
from pathlib import Path

from api.utils.admins_methods import create_admin, _parse_role

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.enums.enums_v1 import AdminRoles

from database.config import AsyncSessionLocal
from database.models.users import Admin


def _prompt(name: str, *, secret: bool = False) -> str:
    value = (getpass if secret else input)(f"{name}: ").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


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
