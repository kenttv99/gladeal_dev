from __future__ import annotations

from fastapi import Request
from sqlalchemy import insert, select, update

from api.enums.enums_v1 import OrderPaymentStates, OrderStates
from api.exceptions import OrderNotFoundError, PaymentInvalidProviderResponseError
from api.payments.utils.xml_response_parser import parse_paygine_response
from database.config import AsyncSessionLocal
from database.models.orders import Order, OrderStatusHistory
from database.models.payments import OrderPaymentData


ORDER_REFERENCE_PREFIX = "gladeal-order-"


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


async def authorize_order_payment_from_webhook(payload: dict[str, object]) -> None:
    order_id = _webhook_order_id(payload)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            current_status = await session.scalar(
                select(Order.status).where(Order.id == order_id).with_for_update()
            )
            if current_status is None:
                raise OrderNotFoundError()

            payment_data_id = await session.scalar(
                update(OrderPaymentData)
                .where(OrderPaymentData.order_id == order_id)
                .values(status=OrderPaymentStates.AUTHORIZED.value)
                .returning(OrderPaymentData.id)
            )
            if payment_data_id is None:
                raise OrderNotFoundError()

            current_status_value = (
                current_status.value if isinstance(current_status, OrderStates) else current_status
            )
            if current_status_value == OrderStates.AWAITING_PERFORMER_CONFIRMATION.value:
                return

            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(status=OrderStates.AWAITING_PERFORMER_CONFIRMATION.value)
            )
            await session.execute(
                insert(OrderStatusHistory).values(
                    order_id=order_id,
                    old_status=current_status_value,
                    new_status=OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
                    changed_by_user_id=None,
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
