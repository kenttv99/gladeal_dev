from fastapi import APIRouter

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


router = APIRouter()


@router.get("/deals", response_model=list[OrderInfoResponse])
async def deals():
    return await get_active_orders_by_role(UserRoles.PERFORMER)


@router.post("/deal_approve")
async def deal_approve(order: ApproveOrderRequest) -> dict[str, bool]:
    await approve_order(order.order_id, order.performer_id)
    return {"success": True}


@router.post("/deal_confirm")
async def deal_confirm(order: PerformerConfirmOrderRequest) -> dict[str, bool]:
    await performer_confirm_order(order.order_id, order.performer_id)
    return {"success": True}


@router.post("/deal_decline")
async def deal_decline(order: PerformerDeclineOrderRequest) -> dict[str, bool]:
    await performer_decline_order(order.order_id, order.performer_id)
    return {"success": True}


@router.post("/deal_conflict")
async def deal_conflict(order: PerformerConflictOrderRequest) -> dict[str, bool]:
    await performer_conflict_order(order.order_id, order.performer_id)
    return {"success": True}


@router.get("/deals_archive", response_model=list[OrderInfoResponse])
async def deals_archive():
    return await get_performer_closed_orders()
