from dataclasses import dataclass
from secrets import token_urlsafe
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, exists, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import BASE_SITE_LINK, MONTH_SUM_LIMIT_PER_USER
from api.enums.enums_v1 import OrderPaymentStates, OrderStates
from api.exceptions import (
    MonthOrdersLimitExceededError,
    OrderAlreadyAcceptedError,
    OrderNotFoundError,
    OrderPaymentInvalidStatusError,
    OrderSelfExecutionForbiddenError,
    UserNotFoundError,
    ValidationError,
)
from database.models.orders import Order, OrderStatusHistory
from database.models.payments import OrderPaymentData
from database.models.users import User


DEAL_SCREEN_PATH = "active_deal"
ACTIVE_ORDER_STATUSES = (
    OrderStates.AWAITING_PERFORMER.value,
    OrderStates.AWAITING_PAYMENT.value,
    OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
    OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
    OrderStates.AWAITING_CONFLICT.value,
    OrderStates.OPEN_CONFLICT.value,
    OrderStates.AWAITING_PERFORMER_PAYOUT.value,
)
CLOSED_ORDER_STATUSES = (
    OrderStates.SUCCESSFUL_COMPLETION.value,
    OrderStates.UNSUCCESSFUL_COMPLETION.value,
    OrderStates.CANCLED_BY_EXPIRE_TIME.value,
    OrderStates.CONFIRM_BY_EXPIRE_TIME_TO_PERFORMER.value,
    OrderStates.CLOSED_BY_ARBITER_TO_CLIENT.value,
    OrderStates.CLOSED_BY_ARBITER_TO_PERFORMER.value,
)
PERFORMER_DECLINE_ORDER_STATUSES = (
    OrderStates.AWAITING_PAYMENT.value,
    OrderStates.AWAITING_CONFLICT.value,
)


@dataclass(frozen=True)
class ClientConfirmPaymentData:
    current_status: OrderStates | str | None
    performer_id: int
    performer_email: str
    performer_phone: str
    price: Decimal
    title: str
    paygine_payment_operation_id: int


@dataclass(frozen=True)
class RefundMoneyOrderData:
    current_status: OrderStates | str | None
    client_id: int
    customer_email: str
    customer_phone: str
    price: Decimal
    title: str


@dataclass(frozen=True)
class OrderInfoPaymentData:
    order: Order
    customer_email: str | None
    performer_email: str | None


async def generate_order_slug(session: AsyncSession) -> str:
    while True:
        slug = token_urlsafe(16)
        slug_exists = await session.scalar(select(exists().where(Order.slug == slug)))
        if not slug_exists:
            return slug


def generate_order_link(slug: str) -> str:
    return f"{BASE_SITE_LINK.rstrip('/')}/{DEAL_SCREEN_PATH}/{slug}"


def order_status_value(status: OrderStates | str | None) -> str | None:
    return status.value if isinstance(status, OrderStates) else status


def ensure_order_status(
    current_status: OrderStates | str | None,
    allowed_statuses: OrderStates | str | tuple[OrderStates | str, ...],
) -> None:
    status_value = order_status_value(current_status)
    if not isinstance(allowed_statuses, tuple):
        allowed_statuses = (allowed_statuses,)
    if status_value not in {order_status_value(status) for status in allowed_statuses}:
        raise ValidationError()


def order_status_values(status: str) -> dict[str, object]:
    values: dict[str, object] = {"status": status}
    if (
        status == OrderStates.AWAITING_CLIENT_CONFIRMATION.value
        or status in CLOSED_ORDER_STATUSES
    ):
        values["completed_at"] = func.now()
    return values


def ensure_registered_order_payment_status(status: OrderPaymentStates | str | None) -> None:
    ensure_order_payment_status(status, OrderPaymentStates.REGISTERED)


def ensure_order_payment_status(
    status: OrderPaymentStates | str | None,
    expected_status: OrderPaymentStates,
) -> None:
    status_value = status.value if isinstance(status, OrderPaymentStates) else status
    if status_value != expected_status.value:
        raise OrderPaymentInvalidStatusError()


async def ensure_user_exists(session: AsyncSession, user_id: int) -> None:
    user_exists = await session.scalar(select(exists().where(User.id == user_id)))
    if not user_exists:
        raise UserNotFoundError()


async def add_order_status_history(
    session: AsyncSession,
    order_id: int,
    old_status: OrderStates | str | None,
    new_status: str,
    changed_by_user_id: int | None,
) -> None:
    await session.execute(
        insert(OrderStatusHistory).values(
            order_id=order_id,
            old_status=order_status_value(old_status),
            new_status=new_status,
            changed_by_user_id=changed_by_user_id,
        )
    )


async def create_order_record(
    session: AsyncSession,
    client_id: int,
    title: str,
    conditions: str,
    result_requirements: str,
    violation_proof_requirements: str,
    price: Decimal,
    expire_in: datetime,
) -> tuple[Order, str]:
    customer_phone = await session.scalar(select(User.phone_number).where(User.id == client_id))
    if customer_phone is None:
        raise UserNotFoundError()

    limit_check = await check_user_month_orders_limit(session, client_id, price)
    if limit_check["is_limit_exceeded"]:
        raise MonthOrdersLimitExceededError(details=limit_check)

    result = await session.execute(
        insert(Order)
        .values(
            client_id=client_id,
            title=title,
            conditions=conditions,
            result_requirements=result_requirements,
            violation_proof_requirements=violation_proof_requirements,
            slug=await generate_order_slug(session),
            price=price,
            expire_in=expire_in,
            status=OrderStates.AWAITING_PERFORMER.value,
        )
        .returning(Order)
    )
    order = result.scalar_one()
    await add_order_status_history(
        session,
        order.id,
        None,
        OrderStates.AWAITING_PERFORMER.value,
        client_id,
    )
    return order, customer_phone


async def create_order_payment_data(
    session: AsyncSession,
    order_id: int,
    customer_email: str,
    payment_values: dict[str, object],
) -> None:
    await session.execute(
        insert(OrderPaymentData).values(
            order_id=order_id,
            customer_email=customer_email,
            **payment_values,
        )
    )


async def delete_order_record(
    session: AsyncSession,
    order_id: int,
    client_id: int,
) -> None:
    order_query = select(Order.id).where(Order.id == order_id, Order.client_id == client_id)
    await session.execute(
        delete(OrderPaymentData).where(OrderPaymentData.order_id.in_(order_query))
    )
    await session.execute(
        delete(OrderStatusHistory).where(OrderStatusHistory.order_id.in_(order_query))
    )
    await session.execute(
        delete(Order).where(Order.id == order_id, Order.client_id == client_id)
    )


async def get_order_info_payment_data(
    session: AsyncSession,
    *conditions: object,
) -> OrderInfoPaymentData:
    result = await session.execute(
        select(
            Order,
            OrderPaymentData.customer_email,
            OrderPaymentData.performer_email,
        )
        .outerjoin(OrderPaymentData, OrderPaymentData.order_id == Order.id)
        .where(*conditions)
    )
    row = result.one_or_none()
    if row is None:
        raise OrderNotFoundError()

    order, customer_email, performer_email = row
    return OrderInfoPaymentData(
        order=order,
        customer_email=customer_email,
        performer_email=performer_email,
    )


async def get_client_confirm_payment_data(
    session: AsyncSession,
    order_id: int,
    client_id: int,
) -> ClientConfirmPaymentData:
    await ensure_user_exists(session, client_id)
    result = await session.execute(
        select(
            Order.status,
            Order.performer_id,
            Order.price,
            Order.title,
            OrderPaymentData.paygine_payment_operation_id,
            OrderPaymentData.payment_status,
            OrderPaymentData.performer_email,
            User.phone_number,
        )
        .join(OrderPaymentData, OrderPaymentData.order_id == Order.id)
        .join(User, User.id == Order.performer_id, isouter=True)
        .where(Order.id == order_id, Order.client_id == client_id)
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
        payment_operation_id,
        payment_status,
        performer_email,
        performer_phone,
    ) = row
    ensure_order_status(current_status, OrderStates.AWAITING_CLIENT_CONFIRMATION)
    if performer_id is None:
        raise ValidationError()
    if payment_operation_id is None:
        raise OrderNotFoundError()
    if not performer_email:
        raise ValidationError()
    if performer_phone is None:
        raise UserNotFoundError()
    ensure_order_payment_status(payment_status, OrderPaymentStates.COMPLETED)
    return ClientConfirmPaymentData(
        current_status=current_status,
        performer_id=performer_id,
        performer_email=performer_email,
        performer_phone=performer_phone,
        price=price,
        title=title,
        paygine_payment_operation_id=int(payment_operation_id),
    )


async def set_client_confirmed_order_status(
    session: AsyncSession,
    order_id: int,
    current_status: OrderStates | str | None,
    client_id: int,
    payout_operation_id: str,
    expire_payout_at: datetime,
) -> None:
    await session.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(**order_status_values(OrderStates.AWAITING_PERFORMER_PAYOUT.value))
    )
    await add_order_status_history(
        session,
        order_id,
        current_status,
        OrderStates.AWAITING_PERFORMER_PAYOUT.value,
        client_id,
    )
    await session.execute(
        update(OrderPaymentData)
        .where(OrderPaymentData.order_id == order_id)
        .values(
            payment_status=OrderPaymentStates.COMPLETED.value,
            payment_complete_at=func.now(),
            paygine_payout_operation_id=payout_operation_id,
            payout_status=OrderPaymentStates.REGISTERED.value,
            expire_payout_at=expire_payout_at,
        )
    )


async def get_performer_decline_refund_data(
    session: AsyncSession,
    order_id: int,
    performer_id: int,
) -> tuple[int | None, RefundMoneyOrderData]:
    await ensure_user_exists(session, performer_id)
    result = await session.execute(
        select(
            Order.status,
            Order.client_id,
            Order.price,
            Order.title,
            OrderPaymentData.paygine_payment_operation_id,
            OrderPaymentData.payment_status,
            OrderPaymentData.customer_email,
            User.phone_number,
        )
        .join(OrderPaymentData, OrderPaymentData.order_id == Order.id)
        .join(User, User.id == Order.client_id)
        .where(Order.id == order_id, Order.performer_id == performer_id)
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
        payment_operation_id,
        payment_status,
        customer_email,
        customer_phone,
    ) = row
    if client_id == performer_id:
        raise OrderSelfExecutionForbiddenError()
    ensure_order_status(current_status, PERFORMER_DECLINE_ORDER_STATUSES)
    if payment_operation_id is None:
        raise OrderNotFoundError()
    if order_status_value(current_status) == OrderStates.AWAITING_PAYMENT.value:
        ensure_registered_order_payment_status(payment_status)
        return int(payment_operation_id), RefundMoneyOrderData(
            current_status=current_status,
            client_id=client_id,
            customer_email=customer_email,
            customer_phone=customer_phone,
            price=price,
            title=title,
        )
    else:
        ensure_order_payment_status(payment_status, OrderPaymentStates.COMPLETED)
    return None, RefundMoneyOrderData(
        current_status=current_status,
        client_id=client_id,
        customer_email=customer_email,
        customer_phone=customer_phone,
        price=price,
        title=title,
    )


async def set_performer_declined_order_status(
    session: AsyncSession,
    order_id: int,
    current_status: OrderStates | str | None,
    performer_id: int,
    refund_operation_id: str,
) -> None:
    await session.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(**order_status_values(OrderStates.UNSUCCESSFUL_COMPLETION.value))
    )
    await add_order_status_history(
        session,
        order_id,
        current_status,
        OrderStates.UNSUCCESSFUL_COMPLETION.value,
        performer_id,
    )
    await session.execute(
        update(OrderPaymentData)
        .where(OrderPaymentData.order_id == order_id)
        .values(
            revoke_status=OrderPaymentStates.REGISTERED.value,
            paygine_revoked_operation_id=refund_operation_id,
            updated_at=func.now(),
        )
    )


async def get_softdecline_payment_operation_id(
    session: AsyncSession,
    order_id: int,
    client_id: int,
) -> tuple[int, OrderStates | str | None]:
    await ensure_user_exists(session, client_id)
    result = await session.execute(
        select(
            Order.status,
            Order.performer_id,
            OrderPaymentData.paygine_payment_operation_id,
            OrderPaymentData.payment_status,
        )
        .join(OrderPaymentData, OrderPaymentData.order_id == Order.id)
        .where(Order.id == order_id, Order.client_id == client_id)
        .with_for_update()
    )
    row = result.one_or_none()
    if row is None:
        raise OrderNotFoundError()

    current_status, performer_id, payment_operation_id, payment_status = row
    ensure_order_status(
        current_status,
        (
            OrderStates.AWAITING_PERFORMER,
            OrderStates.AWAITING_PAYMENT,
        ),
    )
    if (
        order_status_value(current_status) == OrderStates.AWAITING_PERFORMER.value
        and performer_id is not None
    ):
        raise OrderAlreadyAcceptedError()
    if payment_operation_id is None:
        raise OrderNotFoundError()
    ensure_registered_order_payment_status(payment_status)
    return int(payment_operation_id), current_status


async def set_softdeclined_order_status(
    session: AsyncSession,
    order_id: int,
    current_status: OrderStates | str | None,
    client_id: int,
) -> None:
    await session.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(**order_status_values(OrderStates.UNSUCCESSFUL_COMPLETION.value))
    )
    await add_order_status_history(
        session,
        order_id,
        current_status,
        OrderStates.UNSUCCESSFUL_COMPLETION.value,
        client_id,
    )
    await session.execute(
        update(OrderPaymentData)
        .where(OrderPaymentData.order_id == order_id)
        .values(payment_status=OrderPaymentStates.EXPIRED.value)
    )


async def check_user_month_orders_limit(
    session: AsyncSession,
    user_id: int,
    price: Decimal,
) -> dict[str, bool | str]:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (
        month_start.replace(year=month_start.year + 1, month=1)
        if month_start.month == 12
        else month_start.replace(month=month_start.month + 1)
    )

    month_sum = await session.scalar(
        select(func.coalesce(func.sum(Order.price), 0)).where(
            Order.client_id == user_id,
            Order.created_at >= month_start,
            Order.created_at < next_month,
        )
    )
    current_month_sum = month_sum or Decimal("0")
    delta = current_month_sum + price - MONTH_SUM_LIMIT_PER_USER

    return {
        "is_limit_exceeded": delta > 0,
        "delta": str(max(delta, Decimal("0"))),
    }
