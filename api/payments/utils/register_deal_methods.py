from __future__ import annotations

from decimal import Decimal
from xml.etree import ElementTree

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
from api.schemas.schemas_v1 import RegisterDealPaymentRequest
from database.config import AsyncSessionLocal
from database.models.payments import OrderPaymentData


REGISTER_DEAL_ENDPOINT = "/webapi/Register"
REGISTER_DEAL_SIGNATURE_FIELDS = ("sector", "amount", "currency")
PROVIDER_RESPONSE_PREVIEW_LENGTH = 1000


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
    response_data = (
        {"id": raw_response.strip()}
        if data.mode == 1 and _is_plain_order_id(raw_response)
        else _parse_response(raw_response)
    )
    paygine_order_id = response_data.get("id") or response_data.get("order_id")

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


def _parse_response(raw_response: str) -> dict[str, str]:
    """Парсим и проверяем ответ webapi/Register."""
    response = raw_response.strip().lstrip("\ufeff")
    if not response.startswith("<"):
        raise PaymentInvalidProviderResponseError(
            details={"raw_response": response[:PROVIDER_RESPONSE_PREVIEW_LENGTH]}
        )

    root = ElementTree.fromstring(response)
    data = {_xml_tag_name(child.tag): child.text or "" for child in root}

    if _xml_tag_name(root.tag) != "order":
        raise PaymentInvalidProviderResponseError(
            details={
                "root_tag": _xml_tag_name(root.tag),
                "response_data": data,
                "raw_response": response[:PROVIDER_RESPONSE_PREVIEW_LENGTH],
            }
        )

    if data.get("signature") and not is_valid_signature(
        (child.text or "" for child in root if _xml_tag_name(child.tag) != "signature"),
        data["signature"],
    ):
        raise PaymentInvalidProviderSignatureError()

    return data


def _is_plain_order_id(raw_response: str) -> bool:
    """Проверяем, что ответ mode=1 содержит только id заказа."""
    return raw_response.strip().isdigit()


def _xml_tag_name(tag: str) -> str:
    """Возвращаем имя XML-тега без namespace."""
    return tag.rsplit("}", 1)[-1].lower()
