from fastapi import APIRouter

from api.enums.enums_v1 import UserRoles
from api.schemas.schemas_v1 import OrderInfoResponse
from api.utils.orders_methods import get_active_orders_by_role


router = APIRouter()


@router.get("/deals", response_model=list[OrderInfoResponse])
async def deals():
    return await get_active_orders_by_role(UserRoles.PERFORMER)


@router.post("/deal_approve")
async def deal_approve() -> None:
    pass


@router.post("/deal_confirm")
async def deal_confirm() -> None:
    pass


@router.post("/deal_decline")
async def deal_decline() -> None:
    pass


@router.post("/deal_conflict")
async def deal_conflict() -> None:
    pass


@router.get("/deals_archive")
async def deals_archive() -> None:
    pass
