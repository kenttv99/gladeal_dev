from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from api.enums.enums_v1 import AdminRoles, OrderStates
from api.exceptions import ValidationError
from api.schemas.schemas_v1 import AdminUserResponse, AdminUsersResponse
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


async def get_users(
    users_limit: int,
    users_cursor_created_at: datetime | None = None,
    users_cursor_id: int | None = None,
) -> AdminUsersResponse:
    """Получаем страницу пользователей с полной информацией и счетчиками сделок."""
    if (users_cursor_created_at is None) != (users_cursor_id is None):
        raise ValidationError()

    cursor_filter = (
        (
            or_(
                User.created_at < users_cursor_created_at,
                and_(User.created_at == users_cursor_created_at, User.id < users_cursor_id),
            ),
        )
        if users_cursor_created_at is not None and users_cursor_id is not None
        else ()
    )

    async with AsyncSessionLocal() as session:
        users_result = await session.scalars(
            select(User)
            .where(*cursor_filter)
            .order_by(User.created_at.desc(), User.id.desc())
            .limit(users_limit + 1)
        )
        page_users = list(users_result.all())
        has_more = len(page_users) > users_limit
        users = page_users[:users_limit]
        user_ids = [user.id for user in users]

        counts: dict[int, tuple[int, int, int]] = {}
        if user_ids:
            counts_result = await session.execute(
                select(
                    User.id,
                    func.count(Order.id)
                    .filter(Order.status == OrderStates.SUCCESSFUL_COMPLETION.value)
                    .label("successful_orders_count"),
                    func.count(Order.id)
                    .filter(Order.status == OrderStates.UNSUCCESSFUL_COMPLETION.value)
                    .label("unsuccessful_orders_count"),
                    func.count(Order.id)
                    .filter(Order.status == OrderStates.OPEN_CONFLICT.value)
                    .label("conflict_orders_count"),
                )
                .outerjoin(Order, or_(Order.client_id == User.id, Order.performer_id == User.id))
                .where(User.id.in_(user_ids))
                .group_by(User.id)
            )
            counts = {
                user_id: (
                    successful_orders_count,
                    unsuccessful_orders_count,
                    conflict_orders_count,
                )
                for (
                    user_id,
                    successful_orders_count,
                    unsuccessful_orders_count,
                    conflict_orders_count,
                ) in counts_result.all()
            }

    items = [
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
            successful_orders_count=counts.get(user.id, (0, 0, 0))[0],
            unsuccessful_orders_count=counts.get(user.id, (0, 0, 0))[1],
            conflict_orders_count=counts.get(user.id, (0, 0, 0))[2],
        )
        for user in users
    ]

    return AdminUsersResponse(
        limit=users_limit,
        has_more=has_more,
        next_cursor_created_at=items[-1].created_at if has_more else None,
        next_cursor_id=items[-1].id if has_more else None,
        items=items,
    )


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
