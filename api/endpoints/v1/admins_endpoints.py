from datetime import datetime

from fastapi import APIRouter, Query

from api.enums.enums_v1 import OrderStates
from api.schemas.schemas_v1 import (
    AdminOrderInfoResponse,
    AdminOrdersResponse,
    AdminUserBanResponse,
    AdminUsersResponse,
)
from api.utils.admins_methods import (
    get_order_info as get_order_info_method,
    get_orders as get_orders_method,
    get_users as get_users_method,
    set_user_ban_state,
)


router = APIRouter()


@router.get("/get_users")
async def get_users(
    users_limit: int = Query(20, ge=1, le=100),
    users_cursor_created_at: datetime | None = None,
    users_cursor_id: int | None = Query(None, ge=1),
) -> AdminUsersResponse:
    """Получаем всех пользователей с общей информацией и счетчиками сделок."""
    return await get_users_method(users_limit, users_cursor_created_at, users_cursor_id)

@router.get("/get_orders")
async def get_orders(
    orders_limit: int = Query(20, ge=1, le=100),
    orders_cursor_created_at: datetime | None = None,
    orders_cursor_id: int | None = Query(None, ge=1),
    client_id: int | None = Query(None, ge=1),
    performer_id: int | None = Query(None, ge=1),
    status: OrderStates | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    completed_from: datetime | None = None,
    completed_to: datetime | None = None,
) -> AdminOrdersResponse:
    """Получаем список сделок с пагинацией и параллельной фильтрацией."""
    return await get_orders_method(
        orders_limit=orders_limit,
        orders_cursor_created_at=orders_cursor_created_at,
        orders_cursor_id=orders_cursor_id,
        client_id=client_id,
        performer_id=performer_id,
        status=status,
        created_from=created_from,
        created_to=created_to,
        completed_from=completed_from,
        completed_to=completed_to,
    )

@router.get("/get_order_info")
async def get_order_info(order_id: int = Query(..., ge=1)) -> AdminOrderInfoResponse:
    """Получаем полную информацию о сделке и историю статусов."""
    return await get_order_info_method(order_id)

@router.get("/get_balance")
async def get_balance():
    pass

@router.get("/close_to_client")
async def close_to_client():
    pass

@router.get("/close_to_performer")
async def close_to_performer():
    pass


@router.get("/ban_user")
async def ban_user(
    user_id: int = Query(..., ge=1),
    ban_reason: str | None = None,
) -> AdminUserBanResponse:
    """Баним пользователя с сохранением причины."""
    return await set_user_ban_state(user_id, True, ban_reason)


@router.get("/unban_user")
async def unban_user(user_id: int = Query(..., ge=1)) -> AdminUserBanResponse:
    """Снимаем бан пользователя."""
    return await set_user_ban_state(user_id, False)
