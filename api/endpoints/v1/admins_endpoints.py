from datetime import datetime

from fastapi import APIRouter, Body, Depends, Query

from api.enums.enums_v1 import OrderStates
from api.payments.payments_methods import get_balance as get_balance_method
from api.schemas.schemas_v1 import (
    AdminOrderInfoResponse,
    AdminOrdersResponse,
    AdminUserBanResponse,
    AdminUsersResponse,
    AuthAdminResponse,
)
from api.utils.admins_methods import (
    authenticate_admin,
    close_order_to_client,
    close_order_to_performer,
    get_order_info as get_order_info_method,
    get_orders as get_orders_method,
    get_users as get_users_method,
    set_user_ban_state,
)
from api.utils.jwt_methods import (
    authorize_admin,
    create_admin_refresh_token,
    generate_admin_access_token,
    revoke_admin_refresh_token,
)


router = APIRouter()


@router.get("/get_users")
async def get_users(
    users_limit: int = Query(20, ge=1, le=100),
    users_cursor_created_at: datetime | None = None,
    users_cursor_id: int | None = Query(None, ge=1),
    _authorized_admin_id: int = Depends(authorize_admin),
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
    _authorized_admin_id: int = Depends(authorize_admin),
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
async def get_order_info(
    order_id: int = Query(..., ge=1),
    _authorized_admin_id: int = Depends(authorize_admin),
) -> AdminOrderInfoResponse:
    """Получаем полную информацию о сделке и историю статусов."""
    return await get_order_info_method(order_id)

@router.get("/get_balance")
async def get_balance(
    _authorized_admin_id: int = Depends(authorize_admin),
) -> dict[str, object]:
    """Получаем баланс кубышки."""
    return await get_balance_method()

@router.post("/close_to_client")
async def close_to_client(
    order_id: int = Query(..., ge=1),
    _authorized_admin_id: int = Depends(authorize_admin),
) -> dict[str, bool]:
    await close_order_to_client(order_id)
    return {"success": True}

@router.post("/close_to_performer")
async def close_to_performer(
    order_id: int = Query(..., ge=1),
    _authorized_admin_id: int = Depends(authorize_admin),
) -> dict[str, bool]:
    await close_order_to_performer(order_id)
    return {"success": True}


@router.post("/ban_user")
async def ban_user(
    user_id: int = Query(..., ge=1),
    ban_reason: str | None = None,
    _authorized_admin_id: int = Depends(authorize_admin),
) -> AdminUserBanResponse:
    """Баним пользователя с сохранением причины."""
    return await set_user_ban_state(user_id, True, ban_reason)


@router.post("/unban_user")
async def unban_user(
    user_id: int = Query(..., ge=1),
    _authorized_admin_id: int = Depends(authorize_admin),
) -> AdminUserBanResponse:
    """Снимаем бан пользователя."""
    return await set_user_ban_state(user_id, False)


@router.post("/login")
async def login(
    email: str = Body(..., embed=True),
    password: str = Body(..., embed=True),
) -> AuthAdminResponse:
    """Авторизуем администратора по email и паролю."""
    admin_id = await authenticate_admin(email, password)
    refresh_token, refresh_token_expires_at = await create_admin_refresh_token(admin_id)
    return AuthAdminResponse(
        access_token=generate_admin_access_token(admin_id),
        refresh_token=refresh_token,
        refresh_token_expires_at=refresh_token_expires_at,
    )


@router.post("/logout")
async def logout(
    refresh_token: str = Body(..., embed=True),
    _authorized_admin_id: int = Depends(authorize_admin),
) -> dict[str, bool]:
    """Удаляем refresh token администратора."""
    await revoke_admin_refresh_token(refresh_token)
    return {"success": True}
