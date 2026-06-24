from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from api.enums.enums_v1 import AdminRoles, OrderPaymentStates, OrderStates
from api.exceptions import (
    InvalidCredentialsError,
    OrderNotFoundError,
    OrderPaymentInvalidStatusError,
    ValidationError,
)
from api.payments.payments_methods import refund_money, register_payout_deal
from api.schemas.schemas_v1 import (
    AdminOrderInfoResponse,
    AdminOrderResponse,
    AdminOrdersResponse,
    AdminOrderStatusHistoryResponse,
    AdminUserBanResponse,
    AdminUserResponse,
    AdminUsersResponse,
    RefundMoneyPaymentRequest,
    RegisterPayoutDealPaymentRequest,
)
from api.utils.help_orders_method import (
    add_order_status_history,
    ensure_order_payment_status,
    ensure_order_status,
    order_status_values,
)
from api.utils.admin_password_methods import (
    hash_admin_password,
    read_admin_password_hash,
    verify_admin_password_hash,
)
from database.config import AsyncSessionLocal
from database.models.orders import Order, OrderStatusHistory
from database.models.payments import OrderPaymentData
from database.models.users import Admin, User


def _parse_role(value: str) -> AdminRoles:
    try:
        return AdminRoles(value.strip().lower())
    except ValueError as exc:
        options = ", ".join(role.value for role in AdminRoles)
        raise ValueError(f"role must be one of: {options}") from exc


async def authenticate_admin(email: str, password: str) -> int:
    """Проверяем email и пароль администратора для авторизации."""
    async with AsyncSessionLocal() as session:
        admin = await session.scalar(select(Admin).where(Admin.email == email))
        if admin is None or not verify_admin_password_hash(password, admin.password_hash):
            raise InvalidCredentialsError()
        return admin.id


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


async def get_orders(
    orders_limit: int,
    orders_cursor_created_at: datetime | None = None,
    orders_cursor_id: int | None = None,
    client_id: int | None = None,
    performer_id: int | None = None,
    status: OrderStates | str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    completed_from: datetime | None = None,
    completed_to: datetime | None = None,
) -> AdminOrdersResponse:
    """Получаем страницу сделок с фильтрацией по пользователям, статусу и датам."""
    if (orders_cursor_created_at is None) != (orders_cursor_id is None):
        raise ValidationError()
    if created_from is not None and created_to is not None and created_from > created_to:
        raise ValidationError()
    if completed_from is not None and completed_to is not None and completed_from > completed_to:
        raise ValidationError()

    status_value = status.value if isinstance(status, OrderStates) else status
    filters = (
        (Order.client_id == client_id,) if client_id is not None else ()
    ) + (
        (Order.performer_id == performer_id,) if performer_id is not None else ()
    ) + (
        (Order.status == status_value,) if status_value is not None else ()
    ) + (
        (Order.created_at >= created_from,) if created_from is not None else ()
    ) + (
        (Order.created_at <= created_to,) if created_to is not None else ()
    ) + (
        (Order.completed_at >= completed_from,) if completed_from is not None else ()
    ) + (
        (Order.completed_at <= completed_to,) if completed_to is not None else ()
    )
    cursor_filter = (
        (
            or_(
                Order.created_at < orders_cursor_created_at,
                and_(Order.created_at == orders_cursor_created_at, Order.id < orders_cursor_id),
            ),
        )
        if orders_cursor_created_at is not None and orders_cursor_id is not None
        else ()
    )

    async with AsyncSessionLocal() as session:
        result = await session.scalars(
            select(Order)
            .where(*filters, *cursor_filter)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .limit(orders_limit + 1)
        )
        page_orders = list(result.all())

    has_more = len(page_orders) > orders_limit
    orders = page_orders[:orders_limit]
    items = [
        AdminOrderResponse(
            order_id=order.id,
            client_id=order.client_id,
            performer_id=order.performer_id,
            status=order.status,
            created_at=order.created_at,
            completed_at=order.completed_at,
        )
        for order in orders
    ]

    return AdminOrdersResponse(
        limit=orders_limit,
        has_more=has_more,
        next_cursor_created_at=items[-1].created_at if has_more else None,
        next_cursor_id=items[-1].order_id if has_more else None,
        items=items,
    )


async def get_order_info(order_id: int) -> AdminOrderInfoResponse:
    """Получаем полную информацию о сделке и историю изменения статусов."""
    async with AsyncSessionLocal() as session:
        order = await session.scalar(select(Order).where(Order.id == order_id))
        if order is None:
            raise OrderNotFoundError()

        history_result = await session.scalars(
            select(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order_id)
            .order_by(OrderStatusHistory.created_at.asc(), OrderStatusHistory.id.asc())
        )
        status_history = list(history_result.all())

    return AdminOrderInfoResponse(
        id=order.id,
        client_id=order.client_id,
        performer_id=order.performer_id,
        title=order.title,
        conditions=order.conditions,
        result_requirements=order.result_requirements,
        violation_proof_requirements=order.violation_proof_requirements,
        slug=order.slug,
        price=order.price,
        status=order.status,
        checked_by_worker_at=order.checked_by_worker_at,
        expire_in=order.expire_in,
        created_at=order.created_at,
        updated_at=order.updated_at,
        completed_at=order.completed_at,
        status_history=[
            AdminOrderStatusHistoryResponse(
                id=history.id,
                order_id=history.order_id,
                old_status=history.old_status,
                new_status=history.new_status,
                changed_by_user_id=history.changed_by_user_id,
                created_at=history.created_at,
            )
            for history in status_history
        ],
    )


async def close_order_to_client(order_id: int) -> None:
    """Закрываем спор в пользу заказчика и регистрируем возврат без комиссии."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(
                    Order.status,
                    Order.client_id,
                    Order.price,
                    Order.title,
                    OrderPaymentData.payment_status,
                    OrderPaymentData.customer_email,
                    OrderPaymentData.paygine_revoked_operation_id,
                    OrderPaymentData.revoke_status,
                    User.phone_number,
                )
                .join(OrderPaymentData, OrderPaymentData.order_id == Order.id)
                .join(User, User.id == Order.client_id)
                .where(Order.id == order_id)
                .with_for_update(of=(Order, OrderPaymentData))
            )
            row = result.one_or_none()
            if row is None:
                raise OrderNotFoundError()

            (
                current_status,
                client_id,
                price,
                title,
                payment_status,
                customer_email,
                refund_operation_id,
                revoke_status,
                customer_phone,
            ) = row
            ensure_order_status(current_status, OrderStates.OPEN_CONFLICT)
            ensure_order_payment_status(payment_status, OrderPaymentStates.COMPLETED)
            ensure_no_active_payment_operation(refund_operation_id, revoke_status)

            refund_result = await refund_money(
                RefundMoneyPaymentRequest(
                    order_id=order_id,
                    client_id=client_id,
                    customer_email=customer_email,
                    customer_phone=customer_phone,
                    amount=price,
                    description=title,
                )
            )
            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(**order_status_values(OrderStates.CLOSED_BY_ARBITER_TO_CLIENT.value))
            )
            await add_order_status_history(
                session,
                order_id,
                current_status,
                OrderStates.CLOSED_BY_ARBITER_TO_CLIENT.value,
                None,
            )
            await session.execute(
                update(OrderPaymentData)
                .where(OrderPaymentData.order_id == order_id)
                .values(
                    paygine_revoked_operation_id=(
                        refund_result.payment_values.paygine_payout_operation_id
                    ),
                    revoke_status=OrderPaymentStates.REGISTERED.value,
                    updated_at=func.now(),
                )
            )


async def close_order_to_performer(order_id: int) -> None:
    """Закрываем спор в пользу исполнителя и регистрируем выплату без комиссии."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(
                    Order.status,
                    Order.performer_id,
                    Order.price,
                    Order.title,
                    OrderPaymentData.payment_status,
                    OrderPaymentData.performer_email,
                    OrderPaymentData.paygine_payout_operation_id,
                    OrderPaymentData.payout_status,
                    User.phone_number,
                )
                .join(OrderPaymentData, OrderPaymentData.order_id == Order.id)
                .join(User, User.id == Order.performer_id)
                .where(Order.id == order_id)
                .with_for_update(of=(Order, OrderPaymentData))
            )
            row = result.one_or_none()
            if row is None:
                raise OrderNotFoundError()

            (
                current_status,
                performer_id,
                price,
                title,
                payment_status,
                performer_email,
                payout_operation_id,
                payout_status,
                performer_phone,
            ) = row
            ensure_order_status(current_status, OrderStates.OPEN_CONFLICT)
            ensure_order_payment_status(payment_status, OrderPaymentStates.COMPLETED)
            ensure_no_active_payment_operation(payout_operation_id, payout_status)
            if performer_id is None or performer_phone is None or not performer_email:
                raise ValidationError()

            payout_result = await register_payout_deal(
                RegisterPayoutDealPaymentRequest(
                    order_id=order_id,
                    performer_id=performer_id,
                    performer_email=performer_email,
                    performer_phone=performer_phone,
                    amount=price,
                    description=title,
                )
            )
            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(**order_status_values(OrderStates.CLOSED_BY_ARBITER_TO_PERFORMER.value))
            )
            await add_order_status_history(
                session,
                order_id,
                current_status,
                OrderStates.CLOSED_BY_ARBITER_TO_PERFORMER.value,
                None,
            )
            await session.execute(
                update(OrderPaymentData)
                .where(OrderPaymentData.order_id == order_id)
                .values(
                    paygine_payout_operation_id=(
                        payout_result.payment_values.paygine_payout_operation_id
                    ),
                    payout_status=OrderPaymentStates.REGISTERED.value,
                    expire_payout_at=payout_result.payment_values.expire_payout_at,
                    updated_at=func.now(),
                )
            )


def ensure_no_active_payment_operation(
    operation_id: str | None,
    status: OrderPaymentStates | str | None,
) -> None:
    status_value = status.value if isinstance(status, OrderPaymentStates) else status
    if operation_id is not None and status_value != OrderPaymentStates.COMPLETED.value:
        raise OrderPaymentInvalidStatusError()


async def set_user_ban_state(
    user_id: int,
    is_banned: bool,
    ban_reason: str | None = None,
) -> AdminUserBanResponse:
    """Устанавливаем или снимаем бан пользователя одним методом."""
    values = (
        {
            "is_banned": True,
            "ban_reason": ban_reason,
            "banned_at": func.now(),
        }
        if is_banned
        else {
            "is_banned": False,
            "ban_reason": None,
            "banned_at": None,
        }
    )

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(**values)
                .returning(User.id, User.is_banned, User.ban_reason, User.banned_at)
            )
            row = result.one_or_none()
            if row is None:
                raise ValidationError()

    return AdminUserBanResponse(
        id=row.id,
        is_banned=row.is_banned,
        ban_reason=row.ban_reason,
        banned_at=row.banned_at,
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
