from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Security
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from jwt import InvalidTokenError

from api.config import JWT_ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, JWT_SECRET_KEY
from api.exceptions import AccessDeniedError, InvalidCredentialsError


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
