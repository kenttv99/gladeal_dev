from fastapi import APIRouter, Depends

from api.enums.enums_v1 import UserRoles
from api.schemas.schemas_v1 import (
    ApproveOrderRequest,
    OrderInfoResponse,
    PerformerConfirmOrderRequest,
    PerformerConflictOrderRequest,
    PerformerDeclineOrderRequest,
)
from api.utils.orders_methods import (
    approve_order,
    get_active_orders_by_role,
    get_performer_closed_orders,
    performer_confirm_order,
    performer_conflict_order,
    performer_decline_order,
)
from api.utils.jwt_methods import authorize_user, ensure_authorized_user_id


router = APIRouter()


@router.get("/deals", response_model=list[OrderInfoResponse])
async def deals(authorized_user_id: int = Depends(authorize_user)):
    return await get_active_orders_by_role(UserRoles.PERFORMER, authorized_user_id)


@router.post("/deal_approve")
async def deal_approve(
    order: ApproveOrderRequest,
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    ensure_authorized_user_id(order.performer_id, authorized_user_id)
    await approve_order(order.order_id, order.performer_id)
    return {"success": True}


@router.post("/deal_confirm")
async def deal_confirm(
    order: PerformerConfirmOrderRequest,
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    ensure_authorized_user_id(order.performer_id, authorized_user_id)
    await performer_confirm_order(order.order_id, order.performer_id)
    return {"success": True}


@router.post("/deal_decline")
async def deal_decline(
    order: PerformerDeclineOrderRequest,
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    ensure_authorized_user_id(order.performer_id, authorized_user_id)
    await performer_decline_order(order.order_id, order.performer_id)
    return {"success": True}


@router.post("/deal_conflict")
async def deal_conflict(
    order: PerformerConflictOrderRequest,
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    ensure_authorized_user_id(order.performer_id, authorized_user_id)
    await performer_conflict_order(order.order_id, order.performer_id)
    return {"success": True}


@router.get("/deals_archive", response_model=list[OrderInfoResponse])
async def deals_archive(authorized_user_id: int = Depends(authorize_user)):
    return await get_performer_closed_orders(authorized_user_id)
