from fastapi import APIRouter, Body, Depends

from api.schemas.schemas_v1 import (
    AccessTokenRefreshResponse,
    AuthUserResponse,
    RegisterUserRequest,
)
from api.utils.jwt_methods import (
    authorize_user,
    create_refresh_token,
    generate_access_token,
    refresh_access_token,
    revoke_refresh_token,
)
from api.utils.users_methods import (
    authenticate_user,
    delete_account as delete_account_method,
    register_user,
    reset_phone_number as reset_phone_number_method,
)


router = APIRouter()


@router.post("/register")
async def register(user: RegisterUserRequest):
    return await register_user(**user.dict())


@router.post("/delete-account")
async def delete_account(
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    await delete_account_method(authorized_user_id)
    return {"success": True}


@router.post("/login")
async def auth(phone_number: str = Body(..., embed=True)) -> AuthUserResponse:
    user_id = await authenticate_user(phone_number)
    refresh_token, refresh_token_expires_at = await create_refresh_token(user_id)
    return AuthUserResponse(
        access_token=generate_access_token(user_id),
        refresh_token=refresh_token,
        refresh_token_expires_at=refresh_token_expires_at,
    )


@router.post("/access_token_refresh/")
async def access_token_refresh(
    refresh_token: str = Body(..., embed=True),
) -> AccessTokenRefreshResponse:
    return AccessTokenRefreshResponse(
        access_token=await refresh_access_token(refresh_token)
    )


@router.post("/logout/")
async def logout(refresh_token: str = Body(..., embed=True)) -> dict[str, bool]:
    await revoke_refresh_token(refresh_token)
    return {"success": True}


@router.post("/reset-phone-number")
async def reset_phone_number(
    phone_number: str = Body(..., embed=True),
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    await reset_phone_number_method(authorized_user_id, phone_number)
    return {"success": True}
