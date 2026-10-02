from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Literal

from fastapi import Request
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.enums.enums_v1 import OrderPaymentStates, OrderStates
from api.exceptions import (
    OrderNotFoundError,
    PaymentInvalidProviderResponseError,
    PaymentInvalidProviderSignatureError,
)
from api.payments.auth_methods import is_valid_signature
from api.payments.utils.xml_response_parser import parse_paygine_response, xml_leaf_values
from api.utils.help_orders_method import (
    add_order_status_history,
    order_status_value,
    order_status_values,
)
from database.config import AsyncSessionLocal
from database.models.orders import Order
from database.models.payments import OrderPaymentData


ORDER_REFERENCE_PREFIX = "gladeal-order-"
WEBHOOK_SIGNATURE_KEY = "signature"
PAYMENT_DELAY_GRACE_PERIOD_HOURS = 3
WebhookOperationType = Literal["payment", "payout", "refund"]


@dataclass(frozen=True)
class WebhookOrderOperation:
    order_id: int
    payment_data_id: int
    order_status: OrderStates | str | None
    payment_status: OrderPaymentStates | str | None
    payout_status: OrderPaymentStates | str | None
    revoke_status: OrderPaymentStates | str | None
    payment_operation_id: int | None
    operation_type: WebhookOperationType
    created_at: datetime | None = None
    expire_in: datetime | None = None


async def read_order_status_webhook_payload(request: Request) -> dict[str, object]:
    """Читаем XML callback Paygine без бизнес-обработки."""
    body = await request.body()
    payload = parse_paygine_response(body.decode("utf-8"))
    validate_order_status_webhook_signature(payload)
    return payload


def validate_order_status_webhook_signature(payload: dict[str, object]) -> None:
    data = _webhook_data(payload)
    signature = data.get(WEBHOOK_SIGNATURE_KEY)
    if not isinstance(signature, str) or not is_valid_signature(
        xml_leaf_values(data, excluded_keys={WEBHOOK_SIGNATURE_KEY}),
        signature,
    ):
        raise PaymentInvalidProviderSignatureError(details=payload)


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
                if operation.operation_type == "payout":
                    await set_webhook_payout_completed(session, operation)
                else:
                    await set_webhook_refund_completed(session, operation)


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
            OrderPaymentData.payout_status,
            OrderPaymentData.revoke_status,
            OrderPaymentData.paygine_payment_operation_id,
            OrderPaymentData.paygine_payout_operation_id,
            OrderPaymentData.paygine_revoked_operation_id,
            Order.created_at,
            Order.expire_in,
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
        payout_status,
        revoke_status,
        payment_operation_id,
        payout_operation_id,
        revoked_operation_id,
        created_at,
        expire_in,
    ) = row
    return WebhookOrderOperation(
        order_id=order_id,
        payment_data_id=payment_data_id,
        order_status=order_status,
        payment_status=payment_status,
        payout_status=payout_status,
        revoke_status=revoke_status,
        payment_operation_id=int(payment_operation_id) if payment_operation_id is not None else None,
        operation_type=get_webhook_order_operation_type(
            payment_operation_id,
            payout_operation_id,
            revoked_operation_id,
            paygine_order_id,
            payload,
        ),
        created_at=created_at,
        expire_in=expire_in,
    )


def get_webhook_order_operation_type(
    payment_operation_id: str | None,
    payout_operation_id: str | None,
    revoked_operation_id: str | None,
    paygine_order_id: str,
    payload: dict[str, object],
) -> WebhookOperationType:
    if payment_operation_id is not None and str(payment_operation_id) == paygine_order_id:
        return "payment"
    if payout_operation_id is not None and str(payout_operation_id) == paygine_order_id:
        return "payout"
    if revoked_operation_id is not None and str(revoked_operation_id) == paygine_order_id:
        return "refund"
    raise PaymentInvalidProviderResponseError(details=payload)


async def set_webhook_payment_status(
    session: AsyncSession,
    operation: WebhookOrderOperation,
    order_state: str,
) -> None:
    if order_state == OrderPaymentStates.AUTHORIZED.value:
        await set_webhook_payment_authorized(session, operation)
    elif order_state == OrderPaymentStates.COMPLETED.value:
        await set_webhook_payment_completed(session, operation)


def calculate_delayed_order_expire_in(
    created_at: datetime | None,
    current_expire_in: datetime | None,
    payment_at: datetime,
    grace_period_hours: int = PAYMENT_DELAY_GRACE_PERIOD_HOURS,
) -> datetime | None:
    """Сдвигаем дедлайн сделки на задержку оплаты, если оплата произведена позже grace_period_hours."""
    if created_at is None or current_expire_in is None:
        return current_expire_in
    if payment_at.tzinfo is None and created_at.tzinfo is not None:
        payment_at = payment_at.replace(tzinfo=timezone.utc)
    elif payment_at.tzinfo is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    elapsed = payment_at - created_at
    threshold = timedelta(hours=grace_period_hours)
    if elapsed > threshold:
        delay = elapsed - threshold
        return current_expire_in + delay
    return current_expire_in


async def transition_order_to_performer_confirmation(
    session: AsyncSession,
    operation: WebhookOrderOperation,
    is_new_state: bool,
) -> None:
    current_status_value = order_status_value(operation.order_status)
    if current_status_value != OrderStates.AWAITING_PAYMENT.value:
        return

    now = datetime.now(timezone.utc)
    new_expire_in = calculate_delayed_order_expire_in(
        operation.created_at,
        operation.expire_in,
        now,
    )
    order_values = {"status": OrderStates.AWAITING_PERFORMER_CONFIRMATION.value}
    if new_expire_in is not None and new_expire_in != operation.expire_in:
        order_values["expire_in"] = new_expire_in

    await session.execute(
        update(Order)
        .where(Order.id == operation.order_id)
        .values(**order_values)
    )
    if is_new_state:
        await add_order_status_history(
            session,
            operation.order_id,
            current_status_value,
            OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
            None,
        )


async def set_webhook_payment_authorized(
    session: AsyncSession,
    operation: WebhookOrderOperation,
) -> None:
    if operation.payment_operation_id is None:
        raise OrderNotFoundError()
    current_payment_status = payment_status_value(operation.payment_status)

    is_new_authorization = current_payment_status != OrderPaymentStates.AUTHORIZED.value
    if current_payment_status != OrderPaymentStates.COMPLETED.value:
        await session.execute(
            update(OrderPaymentData)
            .where(OrderPaymentData.id == operation.payment_data_id)
            .values(
                payment_status=OrderPaymentStates.AUTHORIZED.value,
                payment_authorized_at=func.now(),
                updated_at=func.now(),
            )
        )

    await transition_order_to_performer_confirmation(
        session,
        operation,
        is_new_authorization,
    )


async def set_webhook_payment_completed(
    session: AsyncSession,
    operation: WebhookOrderOperation,
) -> None:
    is_new_payment_completion = (
        payment_status_value(operation.payment_status) != OrderPaymentStates.COMPLETED.value
    )
    await session.execute(
        update(OrderPaymentData)
        .where(OrderPaymentData.id == operation.payment_data_id)
        .values(
            payment_status=OrderPaymentStates.COMPLETED.value,
            payment_complete_at=func.now(),
            updated_at=func.now(),
        )
    )

    await transition_order_to_performer_confirmation(
        session,
        operation,
        is_new_payment_completion,
    )


async def set_webhook_payout_completed(
    session: AsyncSession,
    operation: WebhookOrderOperation,
) -> None:
    current_status = order_status_value(operation.order_status)
    new_status = get_webhook_payout_completed_order_status(current_status)
    is_new_payout_completion = (
        payment_status_value(operation.payout_status) != OrderPaymentStates.COMPLETED.value
    )

    if current_status != new_status:
        await session.execute(
            update(Order)
            .where(Order.id == operation.order_id)
            .values(**order_status_values(new_status))
        )
        if is_new_payout_completion:
            await add_order_status_history(
                session,
                operation.order_id,
                current_status,
                new_status,
                None,
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


async def set_webhook_refund_completed(
    session: AsyncSession,
    operation: WebhookOrderOperation,
) -> None:
    current_status = order_status_value(operation.order_status)
    new_status = get_webhook_refund_completed_order_status(current_status)
    is_new_refund_completion = (
        payment_status_value(operation.revoke_status) != OrderPaymentStates.COMPLETED.value
    )

    if current_status != new_status:
        await session.execute(
            update(Order)
            .where(Order.id == operation.order_id)
            .values(**order_status_values(new_status))
        )
        if is_new_refund_completion:
            await add_order_status_history(
                session,
                operation.order_id,
                current_status,
                new_status,
                None,
            )

    if is_new_refund_completion:
        await session.execute(
            update(OrderPaymentData)
            .where(OrderPaymentData.id == operation.payment_data_id)
            .values(
                revoke_status=OrderPaymentStates.COMPLETED.value,
                revoked_at=func.now(),
                updated_at=func.now(),
            )
        )


def get_webhook_payout_completed_order_status(
    current_status: OrderStates | str | None,
) -> str:
    status = order_status_value(current_status)
    if status in {
        OrderStates.CONFIRM_BY_EXPIRE_TIME_TO_PERFORMER.value,
        OrderStates.CLOSED_BY_ARBITER_TO_PERFORMER.value,
    }:
        return status
    return OrderStates.SUCCESSFUL_COMPLETION.value


def get_webhook_refund_completed_order_status(
    current_status: OrderStates | str | None,
) -> str:
    status = order_status_value(current_status)
    if status in {
        OrderStates.CANCLED_BY_EXPIRE_TIME.value,
        OrderStates.CLOSED_BY_ARBITER_TO_CLIENT.value,
    }:
        return status
    return OrderStates.UNSUCCESSFUL_COMPLETION.value


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


def payment_status_value(status: OrderPaymentStates | str | None) -> str | None:
    return status.value if isinstance(status, OrderPaymentStates) else status
