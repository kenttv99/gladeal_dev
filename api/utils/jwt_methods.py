from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe

import jwt
from fastapi import Security
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from jwt import InvalidTokenError
from sqlalchemy import insert, select

from api.config import (
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_REFRESH_TOKEN_EXPIRE_MINUTES,
    JWT_SECRET_KEY,
)
from api.exceptions import AccessDeniedError, InvalidCredentialsError
from database.config import AsyncSessionLocal
from database.models.users import UserRefreshToken


auth_scheme = HTTPBasic(
    scheme_name="user_id_access_token",
    description="Username = user_id, Password = access_token",
    auto_error=False,
)


def generate_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "user_id": user_id,
            "iat": now,
            "exp": now + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def generate_refresh_token() -> str:
    return token_urlsafe(64)


def get_refresh_token_hash(refresh_token: str) -> str:
    return sha256(refresh_token.encode()).hexdigest()


async def create_refresh_token(user_id: int) -> str:
    refresh_token = generate_refresh_token()
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                insert(UserRefreshToken).values(
                    user_id=user_id,
                    token_hash=get_refresh_token_hash(refresh_token),
                    expires_at=now + timedelta(minutes=JWT_REFRESH_TOKEN_EXPIRE_MINUTES),
                )
            )

    return refresh_token


async def decode_refresh_token(refresh_token: str) -> int:
    async with AsyncSessionLocal() as session:
        user_id = await session.scalar(
            select(UserRefreshToken.user_id).where(
                UserRefreshToken.token_hash == get_refresh_token_hash(refresh_token),
                UserRefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )

    if user_id is None:
        raise InvalidCredentialsError()

    return user_id


async def refresh_access_token(refresh_token: str) -> str:
    return generate_access_token(await decode_refresh_token(refresh_token))


async def authorize_user(
    credentials: HTTPBasicCredentials | None = Security(auth_scheme),
) -> int:
    if credentials is None:
        raise InvalidCredentialsError()

    try:
        request_user_id = int(credentials.username)
        payload = jwt.decode(credentials.password, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        token_user_id = int(payload["user_id"])
    except (KeyError, TypeError, ValueError, InvalidTokenError) as exc:
        raise InvalidCredentialsError() from exc

    if request_user_id != token_user_id:
        raise AccessDeniedError()

    return request_user_id


def ensure_authorized_user_id(request_user_id: int, authorized_user_id: int) -> None:
    if request_user_id != authorized_user_id:
        raise AccessDeniedError()
