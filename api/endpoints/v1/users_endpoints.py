from fastapi import APIRouter

from api.schemas.schemas_v1 import DeleteAccountRequest, RegisterUserRequest
from api.utils.users_methods import delete_account as delete_account_method, register_user


router = APIRouter()


@router.post("/register")
async def register(user: RegisterUserRequest):
    return await register_user(**user.dict())


@router.post("/delete-account")
async def delete_account(user: DeleteAccountRequest) -> dict[str, bool]:
    await delete_account_method(user.user_id)
    return {"success": True}


@router.post("/auth")
async def auth() -> None:
    pass


@router.post("/reset-phone-number")
async def reset_phone_number() -> None:
    pass
