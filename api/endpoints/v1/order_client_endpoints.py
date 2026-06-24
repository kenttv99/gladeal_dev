from fastapi import APIRouter, Depends

from api.enums.enums_v1 import UserRoles
from api.payments.payments_methods import generate_payment_link, generate_withdrow_link
from api.schemas.schemas_v1 import (
    CreateOrderRequest,
    CreateOrderResponse,
    OrderInfoResponse,
    OrderInfoWithPaymentDataResponse,
)
from api.utils.orders_methods import (
    client_confirm_order,
    client_harddecline_order,
    client_softdecline_order,
    create_order,
    get_active_orders_by_role,
    get_client_closed_orders,
    get_order_info_by_id,
    get_order_info_by_slug,
    get_order_link,
    get_order_payment_operation_id,
    get_order_refund_operation_id,
    # payment_order,
)
from api.utils.jwt_methods import authorize_user
from api.utils.users_methods import ensure_user_not_banned


router = APIRouter()


async def authorize_active_user(
    authorized_user_id: int = Depends(authorize_user),
) -> int:
    await ensure_user_not_banned(authorized_user_id)
    return authorized_user_id


@router.get("/order_link")
async def order_link(
    order_id: int,
    authorized_user_id: int = Depends(authorize_active_user),
) -> dict[str, str]:
    return {"link": await get_order_link(order_id, authorized_user_id)}

@router.get("/order_info_by_slug", response_model=OrderInfoWithPaymentDataResponse)
async def order_info_by_slug(
    slug: str,
    authorized_user_id: int = Depends(authorize_active_user),
):
    return await get_order_info_by_slug(slug)


@router.get("/order_info", response_model=OrderInfoWithPaymentDataResponse)
async def order_info(
    order_id: int,
    authorized_user_id: int = Depends(authorize_active_user),
):
    return await get_order_info_by_id(order_id)

@router.get("/deals", response_model=list[OrderInfoResponse])
async def deals(authorized_user_id: int = Depends(authorize_active_user)):
    return await get_active_orders_by_role(UserRoles.CLIENT, authorized_user_id)


@router.post("/deal_create", response_model=CreateOrderResponse)
async def deal_create(
    order: CreateOrderRequest,
    authorized_user_id: int = Depends(authorize_active_user),
):
    return await create_order(client_id=authorized_user_id, **order.model_dump())


# @router.post("/deal_payment")
# async def deal_payment(
#     order_id: int,
#     authorized_user_id: int = Depends(authorize_active_user),
# ) -> dict[str, bool]:
#     await payment_order(order_id, authorized_user_id)
#     return {"success": True}


@router.post("/deal_confirm")
async def deal_confirm(
    order_id: int,
    authorized_user_id: int = Depends(authorize_active_user),
) -> dict[str, bool]:
    await client_confirm_order(order_id, authorized_user_id)
    return {"success": True}


@router.post("/deal_softdecline")
async def deal_softdecline(
    order_id: int,
    authorized_user_id: int = Depends(authorize_active_user),
) -> dict[str, bool]:
    await client_softdecline_order(order_id, authorized_user_id)
    return {"success": True}


@router.post("/deal_harddecline")
async def deal_harddecline(
    order_id: int,
    authorized_user_id: int = Depends(authorize_active_user),
) -> dict[str, bool]:
    await client_harddecline_order(order_id, authorized_user_id)
    return {"success": True}


@router.get("/deals_archive", response_model=list[OrderInfoResponse])
async def deals_archive(authorized_user_id: int = Depends(authorize_active_user)):
    return await get_client_closed_orders(authorized_user_id)

@router.get("/deal_payment_link")
async def deal_payment_link(
    order_id: int,
    authorized_user_id: int = Depends(authorize_active_user),
) -> dict[str, str]:
    operation_id = await get_order_payment_operation_id(order_id, authorized_user_id)
    link = await generate_payment_link(operation_id)
    return {"link": link}


@router.get("/deal_refund_link")
async def deal_refund_link(
    order_id: int,
    authorized_user_id: int = Depends(authorize_active_user),
) -> dict[str, str]:
    operation_id = await get_order_refund_operation_id(order_id, authorized_user_id)
    link = await generate_withdrow_link(operation_id)
    return {"link": link}
