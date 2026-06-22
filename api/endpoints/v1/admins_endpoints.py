from datetime import datetime

from fastapi import APIRouter, Query

from api.schemas.schemas_v1 import AdminUsersResponse
from api.utils.admins_methods import get_users as get_users_method


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
