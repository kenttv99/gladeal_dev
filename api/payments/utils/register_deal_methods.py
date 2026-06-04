from __future__ import annotations

from decimal import Decimal

from sqlalchemy import insert
from sqlalchemy.exc import SQLAlchemyError

from api.enums.enums_v1 import OrderPaymentStates
from api.exceptions import (
    PaymentInvalidProviderResponseError,
    PaymentInvalidProviderSignatureError,
)
from api.payments.auth_methods import build_signature, is_valid_signature
from api.payments.config import PAYGINE_SECTOR
from api.payments.http_client import get_paygine_client
from api.payments.utils.xml_response_parser import (
    XML_TEXT_ROOT,
    XML_TEXT_VALUE_KEY,
    parse_paygine_response,
    xml_leaf_values,
)
from api.schemas.schemas_v1 import RegisterDealPaymentRequest
from database.config import AsyncSessionLocal
from database.models.payments import OrderPaymentData


REGISTER_DEAL_ENDPOINT = "/webapi/Register"
REGISTER_DEAL_SIGNATURE_FIELDS = ("sector", "amount", "currency")


async def create_registered_deal(
    data: RegisterDealPaymentRequest,
) -> dict[str, object]:
    """Регистрируем сделку в ПЦ и сохраняем платежные данные сделки."""
    response = await send_register_deal_request(data)
    await save_order_payment_data(data, str(response["paygine_order_id"]))
    return response


def build_register_deal_payload(
    data: RegisterDealPaymentRequest,
) -> dict[str, object]:
    """Собираем form-urlencoded payload для webapi/Register."""
    payload = {
        "sector": PAYGINE_SECTOR,
        "amount": data.amount,
        "currency": data.currency,
        "reference": data.reference,
        "description": data.description,
        "payer_id": data.customer.client_ref,
        "email": data.customer.email,
        "phone": data.customer.phone,
        "fee": data.fee,
        "url": data.url,
        "failurl": data.failurl,
        "life_period": data.life_period,
        "sd_ref": data.sd_ref,
        "notify_url": data.notify_url,
        "mode": data.mode,
    }
    payload["signature"] = build_signature(
        payload[field] for field in REGISTER_DEAL_SIGNATURE_FIELDS
    )
    return {key: value for key, value in payload.items() if value is not None}


async def send_register_deal_request(
    data: RegisterDealPaymentRequest,
) -> dict[str, object]:
    """Отправляем запрос регистрации заказа в ПЦ Paygine."""
    payload = build_register_deal_payload(data)
    raw_response = await post_register_deal(payload)
    response_data = get_register_deal_response_data(raw_response, data.mode)
    paygine_order_id = response_data.get("id")

    if not paygine_order_id:
        raise PaymentInvalidProviderResponseError(details=response_data)

    return {
        "paygine_order_id": paygine_order_id,
        "signature": str(payload["signature"]),
        "customer_ref": data.customer.client_ref,
        "performer_ref": data.performer.client_ref,
        "response_data": response_data,
        "raw_response": raw_response,
    }


async def save_order_payment_data(
    data: RegisterDealPaymentRequest,
    paygine_order_id: str,
) -> None:
    """Сохраняем платежные данные зарегистрированной сделки в БД."""
    payment_values = {
        "order_id": data.order_id,
        "customer_email": data.customer.email,
        "performer_email": data.performer.email,
        "currency": data.currency,
        "order_amount": Decimal(data.amount) / Decimal("100"),
        "service_fee_amount": data.service_fee_amount,
        "customer_payment_amount": data.customer_payment_amount,
        "performer_payout_amount": data.performer_payout_amount,
        "status": OrderPaymentStates.CREATED.value,
        "paygine_order_id": paygine_order_id,
        "expires_at": data.expires_at,
    }
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(
                    insert(OrderPaymentData).values(**payment_values)
                )
    except SQLAlchemyError as exc:
        setattr(
            exc,
            "payment_data",
            {key: str(value) for key, value in payment_values.items()},
        )
        raise


async def post_register_deal(payload: dict[str, object]) -> str:
    """Выполняем асинхронный HTTP POST к webapi/Register."""
    response = await get_paygine_client().post(
        REGISTER_DEAL_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
    )
    response.raise_for_status()
    return response.text


def get_register_deal_response_data(
    raw_response: str,
    mode: int,
) -> dict[str, object]:
    """Получаем данные успешного ответа webapi/Register."""
    response = parse_paygine_response(raw_response)
    root_tag = response["root_tag"]
    response_data = response["data"]

    if root_tag == XML_TEXT_ROOT:
        return _get_register_deal_text_data(response_data, mode)

    if not isinstance(response_data, dict):
        raise PaymentInvalidProviderResponseError(details=response)

    if root_tag == "error":
        raise PaymentInvalidProviderResponseError(details=response_data)

    if root_tag != "order":
        raise PaymentInvalidProviderResponseError(details=response)

    _validate_register_deal_signature(response_data)
    return response_data


def _get_register_deal_text_data(
    response_data: object,
    mode: int,
) -> dict[str, object]:
    """Получаем данные plain text ответа webapi/Register."""
    order_id = (
        response_data.get(XML_TEXT_VALUE_KEY)
        if isinstance(response_data, dict)
        else None
    )

    if mode == 1 and isinstance(order_id, str) and order_id.isdigit():
        return {"id": order_id}

    raise PaymentInvalidProviderResponseError(details=response_data)


def _validate_register_deal_signature(response_data: dict[str, object]) -> None:
    """Проверяем подпись XML-ответа webapi/Register."""
    signature = response_data.get("signature")
    if not isinstance(signature, str) or not signature:
        return

    if not is_valid_signature(
        xml_leaf_values(response_data, excluded_keys={"signature"}),
        signature,
    ):
        raise PaymentInvalidProviderSignatureError()
