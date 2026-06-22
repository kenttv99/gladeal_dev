from fastapi import APIRouter, Query

from api.enums.enums_v1 import OrderStates
from api.schemas.schemas_v1 import AdminUserResponse
from api.utils.admins_methods import get_users as get_users_method


router = APIRouter()


@router.get("/get_users")
async def get_users(
    orders_limit: int = Query(20, ge=1, le=100),
    orders_offset: int = Query(0, ge=0),
    order_status: OrderStates | None = None,
) -> list[AdminUserResponse]:
    """Получаем всех пользователей с общей информацией и историей сделок."""
    return await get_users_method(orders_limit, orders_offset, order_status)

@router.get("/get_orders")
async def get_orders():
    pass

@router.get("/get_order_info")
async def get_order_info():
    pass

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
async def ban_user():
    pass


@router.get("/unban_user")
async def unban_user():
    pass

