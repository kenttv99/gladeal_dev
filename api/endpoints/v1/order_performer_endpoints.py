from fastapi import APIRouter, Body, Depends

from api.enums.enums_v1 import UserRoles
from api.payments.payments_methods import generate_withdrow_link
from api.schemas.schemas_v1 import (
    OrderInfoResponse,
)
from api.utils.orders_methods import (
    approve_order,
    get_active_orders_by_role,
    get_order_payout_operation_id,
    get_performer_closed_orders,
    performer_confirm_order,
    performer_conflict_order,
    performer_decline_order,
)
from api.utils.jwt_methods import authorize_user
from api.utils.users_methods import ensure_user_not_banned


router = APIRouter()


async def authorize_active_user(
    authorized_user_id: int = Depends(authorize_user),
) -> int:
    await ensure_user_not_banned(authorized_user_id)
    return authorized_user_id


@router.get("/deals", response_model=list[OrderInfoResponse])
async def deals(authorized_user_id: int = Depends(authorize_active_user)):
    return await get_active_orders_by_role(UserRoles.PERFORMER, authorized_user_id)


@router.post("/deal_approve")
async def deal_approve(
    order_id: int,
    performer_email: str | None = Body(None, embed=True),
    authorized_user_id: int = Depends(authorize_active_user),
) -> dict[str, bool]:
    await approve_order(order_id, authorized_user_id, performer_email)
    return {"success": True}


@router.post("/deal_confirm")
async def deal_confirm(
    order_id: int,
    authorized_user_id: int = Depends(authorize_active_user),
) -> dict[str, bool]:
    await performer_confirm_order(order_id, authorized_user_id)
    return {"success": True}


@router.post("/deal_decline")
async def deal_decline(
    order_id: int,
    authorized_user_id: int = Depends(authorize_active_user),
) -> dict[str, bool]:
    await performer_decline_order(order_id, authorized_user_id)
    return {"success": True}


@router.post("/deal_conflict")
async def deal_conflict(
    order_id: int,
    authorized_user_id: int = Depends(authorize_active_user),
) -> dict[str, bool]:
    await performer_conflict_order(order_id, authorized_user_id)
    return {"success": True}


@router.get("/deal_payout_link")
async def deal_payout_link(
    order_id: int,
    authorized_user_id: int = Depends(authorize_active_user),
) -> dict[str, str]:
    operation_id = await get_order_payout_operation_id(order_id, authorized_user_id)
    link = await generate_withdrow_link(operation_id)
    return {"link": link}


@router.get("/deals_archive", response_model=list[OrderInfoResponse])
async def deals_archive(authorized_user_id: int = Depends(authorize_active_user)):
    return await get_performer_closed_orders(authorized_user_id)
