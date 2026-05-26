from fastapi import APIRouter, Depends

from api.enums.enums_v1 import UserRoles
from api.schemas.schemas_v1 import (
    CreateOrderRequest,
    OrderInfoRequest,
    OrderInfoResponse,
    PaymentOrderRequest,
)
from api.utils.orders_methods import (
    create_order,
    get_active_orders_by_role,
    get_order_by_slug,
    get_order_link,
    payment_order,
)


router = APIRouter()


@router.get("/order_link")
async def order_link(order_id: int) -> dict[str, str]:
    return {"link": await get_order_link(order_id)}

@router.get("/order_info", response_model=OrderInfoResponse)
async def order_info(order: OrderInfoRequest = Depends()):
    return await get_order_by_slug(order.slug)

@router.get("/deals", response_model=list[OrderInfoResponse])
async def deals():
    return await get_active_orders_by_role(UserRoles.CLIENT)


@router.post("/deal_create")
async def deal_create(order: CreateOrderRequest):
    return await create_order(**order.dict())


@router.post("/deal_payment")
async def deal_payment(order: PaymentOrderRequest) -> dict[str, bool]:
    await payment_order(order.order_id, order.client_id)
    return {"success": True}


@router.post("/deal_confirm")
async def deal_confirm() -> None:
    pass


@router.post("/deal_softdecline")
async def deal_softdecline() -> None:
    pass


@router.post("/deal_harddecline")
async def deal_harddecline() -> None:
    pass


@router.post("/deal_conflict")
async def deal_conflict() -> None:
    pass


@router.get("/deals_archive")
async def deals_archive() -> None:
    pass
