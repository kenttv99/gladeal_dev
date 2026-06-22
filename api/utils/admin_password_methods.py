from __future__ import annotations

from argon2 import PasswordHasher, Parameters, extract_parameters
from argon2.exceptions import HashingError, InvalidHashError, VerificationError
from argon2.profiles import RFC_9106_LOW_MEMORY

from api.config import ADMIN_PASSWORD_PEPPER


_PASSWORD_HASHER = PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)


def _peppered_password(password: str) -> str:
    return f"{password}{ADMIN_PASSWORD_PEPPER}"


def hash_admin_password(password: str) -> str:
    try:
        return _PASSWORD_HASHER.hash(_peppered_password(password))
    except HashingError as exc:
        raise RuntimeError("Failed to hash admin password") from exc


def read_admin_password_hash(password_hash: str) -> Parameters:
    return extract_parameters(password_hash)


def verify_admin_password_hash(password: str, password_hash: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash, _peppered_password(password))
    except (InvalidHashError, VerificationError):
        return False
