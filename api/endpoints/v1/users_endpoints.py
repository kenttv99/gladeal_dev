from fastapi import APIRouter

from api.schemas.schemas_v1 import RegisterUserRequest
from api.utils.users_methods import register_user


router = APIRouter()


@router.post("/register")
async def register(user: RegisterUserRequest):
    return await register_user(**user.dict())


@router.post("/delete-account")
async def delete_account() -> None:
    pass


@router.post("/auth")
async def auth() -> None:
    pass


@router.post("/reset-phone-number")
async def reset_phone_number() -> None:
    pass
