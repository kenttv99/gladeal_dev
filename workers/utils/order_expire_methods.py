from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import EXPIRE_TIME_TO_COMNFIRM_MINUTES
from api.enums.enums_v1 import OrderPaymentStates, OrderStates
from api.exceptions import OrderNotFoundError, ValidationError
from api.payments.payments_methods import (
    complete_paymented_deal,
    refund_money,
    register_payout_deal,
)
from api.schemas.schemas_v1 import RegisterPayoutDealPaymentRequest
from api.utils.help_orders_method import (
    add_order_status_history,
    ensure_order_payment_status,
    order_status_value,
    order_status_values,
)
from database.models.orders import Order
from database.models.payments import OrderPaymentData
from database.models.users import User


EXPIRED_ORDER_BATCH_SIZE = 1000
WORKER_SLEEP_SECONDS = 60
EXPIRED_ORDER_ACTIONS = ("cancle", "confirm")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExpiredPaymentOrderData:
    current_status: OrderStates | str | None
    paygine_payment_operation_id: int


@dataclass(frozen=True)
class ExpiredPayoutOrderData(ExpiredPaymentOrderData):
    performer_id: int
    performer_email: str
    performer_phone: str
    price: Decimal
    title: str


def worker_check_allowed(now: datetime):
    """Проверяем, можно ли воркеру повторно брать сделку в обработку."""
    check_cutoff = now - timedelta(seconds=WORKER_SLEEP_SECONDS)
    return or_(Order.checked_by_worker_at.is_(None), Order.checked_by_worker_at <= check_cutoff)


async def claim_order_ids(
    session: AsyncSession,
    *conditions,
    order_by,
    checked_at: datetime,
    limit: int,
) -> list[int]:
    """Атомарно выбираем сделки по условиям и фиксируем время проверки воркером."""
    candidate_ids = (
        select(Order.id)
        .where(*conditions, worker_check_allowed(checked_at))
        .order_by(*order_by, Order.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
        .cte("candidate_orders")
    )

    async with session.begin():
        return list(
            (
                await session.scalars(
                    update(Order)
                    .where(Order.id.in_(select(candidate_ids.c.id)))
                    .values(checked_by_worker_at=checked_at)
                    .returning(Order.id)
                )
            ).all()
        )


async def claim_expired_order_ids(
    session: AsyncSession,
    limit: int = EXPIRED_ORDER_BATCH_SIZE,
) -> dict[str, list[int]]:
    """Получаем IDS сделок для отмены и подтверждения."""
    checked_at = datetime.now(timezone.utc)
    confirm_cutoff = checked_at - timedelta(minutes=float(EXPIRE_TIME_TO_COMNFIRM_MINUTES))

    return {
        "cancle": await claim_order_ids(
            session,
            Order.status == OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
            Order.expire_in <= checked_at,
            order_by=(Order.expire_in,),
            checked_at=checked_at,
            limit=limit,
        ),
        "confirm": await claim_order_ids(
            session,
            Order.status == OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
            Order.completed_at.is_not(None),
            Order.completed_at <= confirm_cutoff,
            order_by=(Order.completed_at,),
            checked_at=checked_at,
            limit=limit,
        ),
    }


async def expire_order(session: AsyncSession, order_id: int, act: str) -> None:
    """Выполняем платежное действие по просрочке и затем фиксируем локальный статус."""
    if act == "cancle":
        await expire_cancled_order(session, order_id)
        return
    if act == "confirm":
        await expire_confirmed_order(session, order_id)
        return
    raise ValidationError()


async def expire_cancled_order(session: AsyncSession, order_id: int) -> None:
    async with session.begin():
        order_data = await get_expired_payment_order_data(
            session,
            order_id,
            OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
        )
        await refund_money(order_data.paygine_payment_operation_id)
        await set_expired_order_payment_status(
            session,
            order_id,
            order_data.current_status,
            OrderStates.CANCLED_BY_EXPIRE_TIME.value,
            OrderPaymentStates.BLOCKED.value,
        )


async def expire_confirmed_order(session: AsyncSession, order_id: int) -> None:
    async with session.begin():
        order_data = await get_expired_payout_order_data(session, order_id)
        await complete_paymented_deal(order_data.paygine_payment_operation_id)
        payout_result = await register_payout_deal(
            RegisterPayoutDealPaymentRequest(
                order_id=order_id,
                performer_id=order_data.performer_id,
                performer_email=order_data.performer_email,
                performer_phone=order_data.performer_phone,
                amount=order_data.price,
                description=order_data.title,
            )
        )
        await set_expired_order_payout_status(
            session,
            order_id,
            order_data.current_status,
            payout_result.payment_values.paygine_payout_operation_id,
            payout_result.payment_values.expire_payout_at,
        )


async def get_expired_payment_order_data(
    session: AsyncSession,
    order_id: int,
    expected_status: str,
) -> ExpiredPaymentOrderData:
    result = await session.execute(
        select(
            Order.status,
            OrderPaymentData.paygine_payment_operation_id,
            OrderPaymentData.payment_status,
        )
        .join(OrderPaymentData, OrderPaymentData.order_id == Order.id)
        .where(Order.id == order_id)
        .with_for_update(of=(Order, OrderPaymentData))
    )
    row = result.one_or_none()
    if row is None:
        raise OrderNotFoundError()

    current_status, payment_operation_id, payment_status = row
    if order_status_value(current_status) != expected_status:
        raise ValidationError()
    if payment_operation_id is None:
        raise OrderNotFoundError()
    ensure_order_payment_status(payment_status, OrderPaymentStates.AUTHORIZED)
    return ExpiredPaymentOrderData(current_status, int(payment_operation_id))


async def get_expired_payout_order_data(
    session: AsyncSession,
    order_id: int,
) -> ExpiredPayoutOrderData:
    result = await session.execute(
        select(
            Order.status,
            Order.performer_id,
            Order.price,
            Order.title,
            OrderPaymentData.paygine_payment_operation_id,
            OrderPaymentData.payment_status,
            OrderPaymentData.performer_email,
            OrderPaymentData.paygine_payout_operation_id,
            User.phone_number,
        )
        .join(OrderPaymentData, OrderPaymentData.order_id == Order.id)
        .join(User, User.id == Order.performer_id, isouter=True)
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
        payment_operation_id,
        payment_status,
        performer_email,
        payout_operation_id,
        performer_phone,
    ) = row
    if order_status_value(current_status) != OrderStates.AWAITING_CLIENT_CONFIRMATION.value:
        raise ValidationError()
    if performer_id is None or performer_phone is None or not performer_email:
        raise ValidationError()
    if payment_operation_id is None or payout_operation_id is not None:
        raise OrderNotFoundError()
    ensure_order_payment_status(payment_status, OrderPaymentStates.AUTHORIZED)
    return ExpiredPayoutOrderData(
        current_status=current_status,
        paygine_payment_operation_id=int(payment_operation_id),
        performer_id=performer_id,
        performer_email=performer_email,
        performer_phone=performer_phone,
        price=price,
        title=title,
    )


async def set_expired_order_payment_status(
    session: AsyncSession,
    order_id: int,
    current_status: OrderStates | str | None,
    new_order_status: str,
    new_payment_status: str,
) -> None:
    await session.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(**order_status_values(new_order_status))
    )
    await add_order_status_history(session, order_id, current_status, new_order_status, None)
    await session.execute(
        update(OrderPaymentData)
        .where(OrderPaymentData.order_id == order_id)
        .values(payment_status=new_payment_status, updated_at=func.now())
    )


async def set_expired_order_payout_status(
    session: AsyncSession,
    order_id: int,
    current_status: OrderStates | str | None,
    payout_operation_id: str,
    expire_payout_at: datetime,
) -> None:
    await session.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(**order_status_values(OrderStates.CONFIRM_BY_EXPIRE_TIME_TO_PERFORMER.value))
    )
    await add_order_status_history(
        session,
        order_id,
        current_status,
        OrderStates.CONFIRM_BY_EXPIRE_TIME_TO_PERFORMER.value,
        None,
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
            updated_at=func.now(),
        )
    )


async def process_expired_orders(session: AsyncSession) -> dict[str, int]:
    """Обрабатываем просроченные сделки батчами и возвращаем количество изменений."""
    processed = {act: 0 for act in EXPIRED_ORDER_ACTIONS}

    while True:
        expired_order_ids = await claim_expired_order_ids(session)
        if not any(expired_order_ids.values()):
            return processed

        for act, order_ids in expired_order_ids.items():
            for order_id in order_ids:
                try:
                    await expire_order(session, order_id, act)
                except (OrderNotFoundError, ValidationError):
                    logger.info("Skipped expired order %s with action %s", order_id, act)
                else:
                    processed[act] += 1
