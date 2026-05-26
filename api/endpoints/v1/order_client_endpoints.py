from fastapi import APIRouter, Depends

from api.enums.enums_v1 import UserRoles
from api.schemas.schemas_v1 import (
    ClientConfirmOrderRequest,
    ClientHardDeclineOrderRequest,
    ClientSoftDeclineOrderRequest,
    CreateOrderRequest,
    OrderInfoRequest,
    OrderInfoResponse,
    PaymentOrderRequest,
)
from api.utils.orders_methods import (
    client_confirm_order,
    client_harddecline_order,
    client_softdecline_order,
    create_order,
    get_active_orders_by_role,
    get_client_closed_orders,
    get_order_by_slug,
    get_order_link,
    payment_order,
)
from api.utils.jwt_methods import authorize_user, ensure_authorized_user_id


router = APIRouter()


@router.get("/order_link")
async def order_link(
    order_id: int,
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, str]:
    return {"link": await get_order_link(order_id, authorized_user_id)}

@router.get("/order_info", response_model=OrderInfoResponse)
async def order_info(
    order: OrderInfoRequest = Depends(),
    authorized_user_id: int = Depends(authorize_user),
):
    return await get_order_by_slug(order.slug, authorized_user_id)

@router.get("/deals", response_model=list[OrderInfoResponse])
async def deals(authorized_user_id: int = Depends(authorize_user)):
    return await get_active_orders_by_role(UserRoles.CLIENT, authorized_user_id)


@router.post("/deal_create")
async def deal_create(
    order: CreateOrderRequest,
    authorized_user_id: int = Depends(authorize_user),
):
    ensure_authorized_user_id(order.client_id, authorized_user_id)
    return await create_order(**order.dict())


@router.post("/deal_payment")
async def deal_payment(
    order: PaymentOrderRequest,
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    ensure_authorized_user_id(order.client_id, authorized_user_id)
    await payment_order(order.order_id, order.client_id)
    return {"success": True}


@router.post("/deal_confirm")
async def deal_confirm(
    order: ClientConfirmOrderRequest,
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    ensure_authorized_user_id(order.client_id, authorized_user_id)
    await client_confirm_order(order.order_id, order.client_id)
    return {"success": True}


@router.post("/deal_softdecline")
async def deal_softdecline(
    order: ClientSoftDeclineOrderRequest,
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    ensure_authorized_user_id(order.client_id, authorized_user_id)
    await client_softdecline_order(order.order_id, order.client_id)
    return {"success": True}


@router.post("/deal_harddecline")
async def deal_harddecline(
    order: ClientHardDeclineOrderRequest,
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    ensure_authorized_user_id(order.client_id, authorized_user_id)
    await client_harddecline_order(order.order_id, order.client_id)
    return {"success": True}


@router.get("/deals_archive", response_model=list[OrderInfoResponse])
async def deals_archive(authorized_user_id: int = Depends(authorize_user)):
    return await get_client_closed_orders(authorized_user_id)
