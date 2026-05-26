from fastapi import APIRouter, Depends

from api.schemas.schemas_v1 import (
    AuthUserRequest,
    AuthUserResponse,
    DeleteAccountRequest,
    RegisterUserRequest,
    ResetPhoneNumberRequest,
)
from api.utils.jwt_methods import authorize_user, ensure_authorized_user_id, generate_access_token
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


@router.post("/delete-account", dependencies=[Depends(authorize_user)])
async def delete_account(
    user: DeleteAccountRequest,
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    ensure_authorized_user_id(user.user_id, authorized_user_id)
    await delete_account_method(user.user_id)
    return {"success": True}


@router.post("/login")
async def auth(user: AuthUserRequest) -> AuthUserResponse:
    user_id = await authenticate_user(user.phone_number)
    return AuthUserResponse(access_token=generate_access_token(user_id))


@router.post("/reset-phone-number", dependencies=[Depends(authorize_user)])
async def reset_phone_number(
    user: ResetPhoneNumberRequest,
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    ensure_authorized_user_id(user.user_id, authorized_user_id)
    await reset_phone_number_method(user.user_id, user.phone_number)
    return {"success": True}
