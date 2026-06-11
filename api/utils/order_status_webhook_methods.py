from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fastapi import Request
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.enums.enums_v1 import OrderPaymentStates, OrderStates
from api.exceptions import OrderNotFoundError, PaymentInvalidProviderResponseError
from api.payments.utils.xml_response_parser import parse_paygine_response
from api.utils.help_orders_method import order_status_values
from database.config import AsyncSessionLocal
from database.models.orders import Order, OrderStatusHistory
from database.models.payments import OrderPaymentData


ORDER_REFERENCE_PREFIX = "gladeal-order-"
WebhookOperationType = Literal["payment", "payout"]


@dataclass(frozen=True)
class WebhookOrderOperation:
    order_id: int
    payment_data_id: int
    order_status: OrderStates | str | None
    payment_status: OrderPaymentStates | str | None
    operation_type: WebhookOperationType


async def read_order_status_webhook_payload(request: Request) -> dict[str, object]:
    """Читаем XML callback Paygine без бизнес-обработки."""
    body = await request.body()
    return parse_paygine_response(body.decode("utf-8"))


def get_order_status_webhook_state(payload: dict[str, object]) -> str:
    data = _webhook_data(payload)
    order_state = data.get("order_state")
    if not isinstance(order_state, str):
        raise PaymentInvalidProviderResponseError(details=payload)
    try:
        return OrderPaymentStates(order_state.lower()).value
    except ValueError as exc:
        raise PaymentInvalidProviderResponseError(details=payload) from exc


async def update_order_payment_status_from_webhook(
    payload: dict[str, object],
    order_state: str,
) -> None:
    order_id = _webhook_order_id(payload)
    paygine_order_id = _webhook_paygine_order_id(payload)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            operation = await get_webhook_order_operation(
                session,
                order_id,
                paygine_order_id,
                payload,
            )
            if operation.operation_type == "payment":
                await set_webhook_payment_status(session, operation, order_state)
            elif order_state == OrderPaymentStates.COMPLETED.value:
                await set_webhook_payout_completed(session, operation)


async def get_webhook_order_operation(
    session: AsyncSession,
    order_id: int,
    paygine_order_id: str,
    payload: dict[str, object],
) -> WebhookOrderOperation:
    result = await session.execute(
        select(
            Order.status,
            OrderPaymentData.id,
            OrderPaymentData.payment_status,
            OrderPaymentData.paygine_payment_operation_id,
            OrderPaymentData.paygine_payout_operation_id,
        )
        .join(OrderPaymentData, OrderPaymentData.order_id == Order.id)
        .where(Order.id == order_id)
        .with_for_update(of=(Order, OrderPaymentData))
    )
    row = result.one_or_none()
    if row is None:
        raise OrderNotFoundError()

    (
        order_status,
        payment_data_id,
        payment_status,
        payment_operation_id,
        payout_operation_id,
    ) = row
    return WebhookOrderOperation(
        order_id=order_id,
        payment_data_id=payment_data_id,
        order_status=order_status,
        payment_status=payment_status,
        operation_type=get_webhook_order_operation_type(
            payment_operation_id,
            payout_operation_id,
            paygine_order_id,
            payload,
        ),
    )


def get_webhook_order_operation_type(
    payment_operation_id: str | None,
    payout_operation_id: str | None,
    paygine_order_id: str,
    payload: dict[str, object],
) -> WebhookOperationType:
    if payment_operation_id is not None and str(payment_operation_id) == paygine_order_id:
        return "payment"
    if payout_operation_id is not None and str(payout_operation_id) == paygine_order_id:
        return "payout"
    raise PaymentInvalidProviderResponseError(details=payload)


async def set_webhook_payment_status(
    session: AsyncSession,
    operation: WebhookOrderOperation,
    order_state: str,
) -> None:
    if order_state == OrderPaymentStates.AUTHORIZED.value:
        await set_webhook_payment_authorized(session, operation)
    elif order_state == OrderPaymentStates.COMPLETED.value:
        await session.execute(
            update(OrderPaymentData)
            .where(OrderPaymentData.id == operation.payment_data_id)
            .values(payment_status=OrderPaymentStates.COMPLETED.value, updated_at=func.now())
        )


async def set_webhook_payment_authorized(
    session: AsyncSession,
    operation: WebhookOrderOperation,
) -> None:
    if _enum_value(operation.payment_status) != OrderPaymentStates.COMPLETED.value:
        await session.execute(
            update(OrderPaymentData)
            .where(OrderPaymentData.id == operation.payment_data_id)
            .values(
                payment_status=OrderPaymentStates.AUTHORIZED.value,
                payment_complete_at=func.now(),
                updated_at=func.now(),
            )
        )

    current_status_value = _enum_value(operation.order_status)
    if current_status_value != OrderStates.AWAITING_PAYMENT.value:
        return

    await session.execute(
        update(Order)
        .where(Order.id == operation.order_id)
        .values(status=OrderStates.AWAITING_PERFORMER_CONFIRMATION.value)
    )
    await session.execute(
        insert(OrderStatusHistory).values(
            order_id=operation.order_id,
            old_status=current_status_value,
            new_status=OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
            changed_by_user_id=None,
        )
    )


async def set_webhook_payout_completed(
    session: AsyncSession,
    operation: WebhookOrderOperation,
) -> None:
    await session.execute(
        update(Order)
        .where(Order.id == operation.order_id)
        .values(**order_status_values(OrderStates.SUCCESSFUL_COMPLETION.value))
    )
    await session.execute(
        update(OrderPaymentData)
        .where(OrderPaymentData.id == operation.payment_data_id)
        .values(
            payout_status=OrderPaymentStates.COMPLETED.value,
            payout_completed_at=func.now(),
            updated_at=func.now(),
        )
    )


def _webhook_data(payload: dict[str, object]) -> dict[str, object]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise PaymentInvalidProviderResponseError(details=payload)
    return data


def _webhook_order_id(payload: dict[str, object]) -> int:
    reference = _webhook_data(payload).get("reference")
    if not isinstance(reference, str) or not reference.startswith(ORDER_REFERENCE_PREFIX):
        raise PaymentInvalidProviderResponseError(details=payload)
    try:
        return int(reference.removeprefix(ORDER_REFERENCE_PREFIX).split("-", 1)[0])
    except ValueError as exc:
        raise PaymentInvalidProviderResponseError(details=payload) from exc


def _webhook_paygine_order_id(payload: dict[str, object]) -> str:
    order_id = _webhook_data(payload).get("order_id")
    if not isinstance(order_id, (int, str)):
        raise PaymentInvalidProviderResponseError(details=payload)
    return str(order_id)


def _enum_value(value: object) -> object:
    return value.value if hasattr(value, "value") else value
