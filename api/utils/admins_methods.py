from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import and_, insert, literal, or_, select, true, union_all, update
from sqlalchemy.exc import IntegrityError

from api.enums.enums_v1 import AdminRoles, OrderStates, UserRoles
from api.schemas.schemas_v1 import (
    AdminUserOrderResponse,
    AdminUserOrdersResponse,
    AdminUserResponse,
)
from api.exceptions import ValidationError
from api.utils.admin_password_methods import (
    hash_admin_password,
    read_admin_password_hash,
    verify_admin_password_hash,
)
from database.config import AsyncSessionLocal
from database.models.orders import Order
from database.models.users import Admin, User


def _parse_role(value: str) -> AdminRoles:
    try:
        return AdminRoles(value.strip().lower())
    except ValueError as exc:
        options = ", ".join(role.value for role in AdminRoles)
        raise ValueError(f"role must be one of: {options}") from exc


def _order_status_value(status: OrderStates | str | None) -> str | None:
    return status.value if isinstance(status, OrderStates) else status


async def get_users(
    orders_limit: int,
    orders_cursor_created_at: datetime | None = None,
    orders_cursor_id: int | None = None,
    order_status: OrderStates | str | None = None,
    orders_created_from: datetime | None = None,
    orders_created_to: datetime | None = None,
) -> list[AdminUserResponse]:
    """Получаем всех пользователей с общей информацией и keyset-страницей истории сделок."""
    if (orders_cursor_created_at is None) != (orders_cursor_id is None):
        raise ValidationError()
    if (
        orders_created_from is not None
        and orders_created_to is not None
        and orders_created_from > orders_created_to
    ):
        raise ValidationError()

    status_value = _order_status_value(order_status)
    status_filter = (Order.status == status_value,) if status_value else ()
    created_from_filter = (Order.created_at >= orders_created_from,) if orders_created_from else ()
    created_to_filter = (Order.created_at <= orders_created_to,) if orders_created_to else ()
    order_filters = (*status_filter, *created_from_filter, *created_to_filter)

    client_orders = select(
        Order.client_id.label("user_id"),
        Order.id.label("id"),
        Order.title.label("title"),
        Order.status.label("status"),
        Order.created_at.label("created_at"),
        literal(UserRoles.CLIENT.value).label("user_order_role"),
    ).where(Order.client_id == User.id, *order_filters).correlate(User)
    performer_orders = select(
        Order.performer_id.label("user_id"),
        Order.id.label("id"),
        Order.title.label("title"),
        Order.status.label("status"),
        Order.created_at.label("created_at"),
        literal(UserRoles.PERFORMER.value).label("user_order_role"),
    ).where(Order.performer_id == User.id, *order_filters).correlate(User)
    orders = union_all(client_orders, performer_orders).subquery()
    cursor_filter = (
        (
            or_(
                orders.c.created_at < orders_cursor_created_at,
                and_(orders.c.created_at == orders_cursor_created_at, orders.c.id < orders_cursor_id),
            ),
        )
        if orders_cursor_created_at is not None and orders_cursor_id is not None
        else ()
    )
    user_orders = (
        select(orders)
        .where(*cursor_filter)
        .order_by(orders.c.created_at.desc(), orders.c.id.desc())
        .limit(orders_limit + 1)
        .lateral("user_orders")
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                User,
                user_orders.c.id.label("order_id"),
                user_orders.c.title,
                user_orders.c.status,
                user_orders.c.created_at.label("order_created_at"),
                user_orders.c.user_order_role,
            )
            .outerjoin(user_orders, true())
            .order_by(User.created_at.desc(), user_orders.c.created_at.desc(), user_orders.c.id.desc())
        )

    users: dict[int, User] = {}
    orders_by_user: defaultdict[int, list[AdminUserOrderResponse]] = defaultdict(list)
    has_more_by_user: set[int] = set()
    for row in result.all():
        user = row[0]
        users[user.id] = user
        if row.order_id is None:
            continue
        if len(orders_by_user[user.id]) == orders_limit:
            has_more_by_user.add(user.id)
            continue
        orders_by_user[user.id].append(
            AdminUserOrderResponse(
                id=row.order_id,
                title=row.title,
                status=row.status,
                created_at=row.order_created_at,
                user_order_role=row.user_order_role,
            )
        )

    return [
        AdminUserResponse(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            phone_number=user.phone_number,
            ppd=user.ppd,
            is_banned=user.is_banned,
            ban_reason=user.ban_reason,
            banned_at=user.banned_at,
            role=user.role,
            created_at=user.created_at,
            updated_at=user.updated_at,
            orders=AdminUserOrdersResponse(
                limit=orders_limit,
                has_more=user.id in has_more_by_user,
                next_cursor_created_at=orders_by_user[user.id][-1].created_at
                if user.id in has_more_by_user
                else None,
                next_cursor_id=orders_by_user[user.id][-1].id
                if user.id in has_more_by_user
                else None,
                items=orders_by_user[user.id],
            ),
        )
        for user in users.values()
    ]


async def create_admin(first_name: str, last_name: str, email: str, role: str, password: str) -> int:
    '''Создаем админа с нужной ролью'''
    role_value = _parse_role(role)
    password_hash = hash_admin_password(password)
    read_admin_password_hash(password_hash)
    if not verify_admin_password_hash(password, password_hash):
        raise RuntimeError("Password hash verification failed")

    async with AsyncSessionLocal() as session:
        try:
            async with session.begin():
                result = await session.execute(
                    insert(Admin)
                    .values(
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        role=role_value,
                        password_hash=password_hash,
                    )
                    .returning(Admin.id)
                )
                return result.scalar_one()
        except IntegrityError as exc:
            if "uq_admins_email" in str(exc.orig):
                raise ValueError("Admin with this email already exists") from exc
            raise

async def change_admin_password_by_email(email: str, password: str) -> int:
    '''Меняем пароль у сущесвтующего админа'''
    password_hash = hash_admin_password(password)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                update(Admin)
                .where(Admin.email == email)
                .values(password_hash=password_hash)
                .returning(Admin.id)
            )
            admin_id = result.scalar_one_or_none()
            if admin_id is None:
                raise ValueError("Admin with this email does not exist")
            return admin_id
