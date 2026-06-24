from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe

import jwt
from fastapi import Security
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import insert, select

from api.config import (
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_REFRESH_TOKEN_EXPIRE_MINUTES,
    JWT_SECRET_KEY,
)
from api.exceptions import (
    AccessDeniedError,
    AccessTokenExpiredError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshTokenExpiredError,
)
from database.config import AsyncSessionLocal
from database.models.users import AdminRefreshToken, UserRefreshToken


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


def generate_admin_access_token(admin_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(admin_id),
            "admin_id": admin_id,
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


async def create_refresh_token(user_id: int) -> tuple[str, datetime]:
    refresh_token = generate_refresh_token()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=JWT_REFRESH_TOKEN_EXPIRE_MINUTES)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                insert(UserRefreshToken).values(
                    user_id=user_id,
                    token_hash=get_refresh_token_hash(refresh_token),
                    expires_at=expires_at,
                )
            )

    return refresh_token, expires_at


async def create_admin_refresh_token(admin_id: int) -> tuple[str, datetime]:
    refresh_token = generate_refresh_token()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=JWT_REFRESH_TOKEN_EXPIRE_MINUTES)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                insert(AdminRefreshToken).values(
                    admin_id=admin_id,
                    token_hash=get_refresh_token_hash(refresh_token),
                    expires_at=expires_at,
                )
            )

    return refresh_token, expires_at


async def decode_refresh_token(refresh_token: str) -> int:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        token = await session.scalar(
            select(UserRefreshToken).where(
                UserRefreshToken.token_hash == get_refresh_token_hash(refresh_token)
            )
        )

    if token is None:
        raise InvalidRefreshTokenError()

    if token.expires_at <= now:
        raise RefreshTokenExpiredError()

    return token.user_id


async def refresh_access_token(refresh_token: str) -> str:
    return generate_access_token(await decode_refresh_token(refresh_token))


async def revoke_refresh_token(refresh_token: str) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            token = await session.scalar(
                select(UserRefreshToken).where(
                    UserRefreshToken.token_hash == get_refresh_token_hash(refresh_token)
                )
            )
            if token is None:
                raise InvalidRefreshTokenError()
            await session.delete(token)


async def revoke_admin_refresh_token(refresh_token: str) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            token = await session.scalar(
                select(AdminRefreshToken).where(
                    AdminRefreshToken.token_hash == get_refresh_token_hash(refresh_token)
                )
            )
            if token is None:
                raise InvalidRefreshTokenError()
            await session.delete(token)


async def authorize_user(
    credentials: HTTPBasicCredentials | None = Security(auth_scheme),
) -> int:
    if credentials is None:
        raise InvalidCredentialsError()

    try:
        request_user_id = int(credentials.username)
        payload = jwt.decode(credentials.password, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        token_user_id = int(payload["user_id"])
    except ExpiredSignatureError as exc:
        raise AccessTokenExpiredError() from exc
    except InvalidTokenError as exc:
        raise InvalidAccessTokenError() from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidAccessTokenError() from exc

    if request_user_id != token_user_id:
        raise AccessDeniedError()

    return request_user_id


async def authorize_admin(
    credentials: HTTPBasicCredentials | None = Security(auth_scheme),
) -> int:
    if credentials is None:
        raise InvalidCredentialsError()

    try:
        request_admin_id = int(credentials.username)
        payload = jwt.decode(credentials.password, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        token_admin_id = int(payload["admin_id"])
    except ExpiredSignatureError as exc:
        raise AccessTokenExpiredError() from exc
    except InvalidTokenError as exc:
        raise InvalidAccessTokenError() from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidAccessTokenError() from exc

    if request_admin_id != token_admin_id:
        raise AccessDeniedError()

    return request_admin_id


def ensure_authorized_user_id(request_user_id: int, authorized_user_id: int) -> None:
    if request_user_id != authorized_user_id:
        raise AccessDeniedError()
