from fastapi import APIRouter


router = APIRouter()


@router.get("/success")
async def redirect_after_payment_success() -> None:
    pass


@router.get("/failure")
async def redirect_after_payment_failure() -> None:
    pass
