from fastapi import APIRouter


router = APIRouter()


@router.post("/register")
async def register() -> None:
    pass


@router.post("/delete-account")
async def delete_account() -> None:
    pass


@router.post("/auth")
async def auth() -> None:
    pass


@router.post("/reset-phone-number")
async def reset_phone_number() -> None:
    pass
