from __future__ import annotations

import argparse
import asyncio
import sys
from getpass import getpass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.utils.admins_methods import change_admin_password_by_email


def _prompt(name: str, *, secret: bool = False) -> str:
    value = (getpass if secret else input)(f"{name}: ").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


async def main() -> None:
    parser = argparse.ArgumentParser(description="Change admin password by email")
    parser.add_argument("--email")
    parser.add_argument("--password")
    parser.add_argument("--confirm-password")
    args = parser.parse_args()

    email = args.email or _prompt("email")
    password = args.password or _prompt("password", secret=True)
    password_confirm = args.confirm_password or _prompt("confirm_password", secret=True)
    if password != password_confirm:
        raise ValueError("password confirmation does not match")

    admin_id = await change_admin_password_by_email(email, password)
    print(f"admin_password_updated id={admin_id} email={email}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ValueError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
