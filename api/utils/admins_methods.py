from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, insert, literal, select, union_all, update
from sqlalchemy.exc import IntegrityError

from api.enums.enums_v1 import AdminRoles, OrderStates, UserRoles
from api.schemas.schemas_v1 import (
    AdminUserOrderResponse,
    AdminUserOrdersResponse,
    AdminUserResponse,
)
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
    orders_offset: int,
    order_status: OrderStates | str | None = None,
) -> list[AdminUserResponse]:
    """Получаем всех пользователей с общей информацией и страницей истории сделок."""
    status_value = _order_status_value(order_status)
    status_filter = (Order.status == status_value,) if status_value else ()

    client_orders = select(
        Order.client_id.label("user_id"),
        Order.id.label("id"),
        Order.title.label("title"),
        Order.status.label("status"),
        Order.created_at.label("created_at"),
        literal(UserRoles.CLIENT.value).label("user_order_role"),
    ).where(*status_filter)
    performer_orders = select(
        Order.performer_id.label("user_id"),
        Order.id.label("id"),
        Order.title.label("title"),
        Order.status.label("status"),
        Order.created_at.label("created_at"),
        literal(UserRoles.PERFORMER.value).label("user_order_role"),
    ).where(Order.performer_id.is_not(None), *status_filter)
    orders = union_all(client_orders, performer_orders).subquery()
    ranked_orders = select(
        orders,
        func.row_number()
        .over(partition_by=orders.c.user_id, order_by=orders.c.created_at.desc())
        .label("row_number"),
    ).subquery()

    async with AsyncSessionLocal() as session:
        users_result = await session.execute(select(User).order_by(User.created_at.desc()))
        users = list(users_result.scalars().all())

        totals_result = await session.execute(
            select(orders.c.user_id, func.count().label("total")).group_by(orders.c.user_id)
        )
        totals: dict[int, int] = {
            int(row.user_id): int(row.total)
            for row in totals_result.mappings().all()
            if row["user_id"] is not None
        }

        orders_result = await session.execute(
            select(ranked_orders)
            .where(
                ranked_orders.c.row_number > orders_offset,
                ranked_orders.c.row_number <= orders_offset + orders_limit,
            )
            .order_by(ranked_orders.c.user_id, ranked_orders.c.row_number)
        )

    orders_by_user = defaultdict(list)
    for order in orders_result.mappings().all():
        orders_by_user[order["user_id"]].append(
            AdminUserOrderResponse(
                id=order["id"],
                title=order["title"],
                status=order["status"],
                user_order_role=order["user_order_role"],
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
                offset=orders_offset,
                total=totals.get(int(user.id), 0),
                items=orders_by_user[user.id],
            ),
        )
        for user in users
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
