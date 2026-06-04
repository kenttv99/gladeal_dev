from __future__ import annotations

import asyncio
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from sqlalchemy import insert

from api.enums.enums_v1 import OrderPaymentStates
from api.payments.auth_methods import build_signature, is_valid_signature
from api.payments.config import (
    PAYGINE_BASE_URL,
    PAYGINE_REQUEST_TIMEOUT_SECONDS,
    PAYGINE_SECTOR,
)
from api.schemas.schemas_v1 import (
    RegisterDealPaymentRequest,
    RegisterDealPaymentResponse,
)
from database.config import AsyncSessionLocal
from database.models.payments import OrderPaymentData


REGISTER_DEAL_ENDPOINT = "/webapi/Register"
REGISTER_DEAL_SIGNATURE_FIELDS = ("sector", "amount", "currency")


class RegisterDealError(RuntimeError):
    pass


async def create_registered_deal(
    data: RegisterDealPaymentRequest,
) -> RegisterDealPaymentResponse:
    """Регистрируем сделку в ПЦ и сохраняем платежные данные сделки."""
    response = await send_register_deal_request(data)
    await save_order_payment_data(data, response.paygine_order_id)
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
) -> RegisterDealPaymentResponse:
    """Отправляем запрос регистрации заказа в ПЦ Paygine."""
    payload = build_register_deal_payload(data)
    raw_response = await asyncio.to_thread(_post_register_deal, payload)
    response_data = _parse_response(raw_response)
    paygine_order_id = response_data.get("id") or (
        raw_response.strip() if data.mode == 1 else None
    )

    if not paygine_order_id:
        raise RegisterDealError(raw_response)

    return RegisterDealPaymentResponse(
        paygine_order_id=paygine_order_id,
        signature=str(payload["signature"]),
        customer_ref=data.customer.client_ref,
        performer_ref=data.performer.client_ref,
        response_data=response_data,
        raw_response=raw_response,
    )


async def save_order_payment_data(
    data: RegisterDealPaymentRequest,
    paygine_order_id: str,
) -> None:
    """Сохраняем платежные данные зарегистрированной сделки в БД."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                insert(OrderPaymentData).values(
                    order_id=data.order_id,
                    customer_email=data.customer.email,
                    performer_email=data.performer.email,
                    currency=data.currency,
                    order_amount=Decimal(data.amount) / Decimal("100"),
                    service_fee_amount=data.service_fee_amount,
                    customer_payment_amount=data.customer_payment_amount,
                    performer_payout_amount=data.performer_payout_amount,
                    status=OrderPaymentStates.CREATED.value,
                    paygine_order_id=paygine_order_id,
                    expires_at=data.expires_at,
                )
            )


def _post_register_deal(payload: dict[str, object]) -> str:
    """Выполняем синхронный HTTP POST к webapi/Register."""
    request = Request(
        f"{PAYGINE_BASE_URL}{REGISTER_DEAL_ENDPOINT}",
        data=urlencode(payload).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
    )
    with urlopen(request, timeout=PAYGINE_REQUEST_TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _parse_response(raw_response: str) -> dict[str, str]:
    """Парсим и проверяем ответ webapi/Register."""
    if not raw_response.lstrip().startswith("<"):
        return {}

    root = ElementTree.fromstring(raw_response)
    data = {child.tag: child.text or "" for child in root}

    if root.tag.lower() != "order":
        raise RegisterDealError(raw_response)

    if data.get("signature") and not is_valid_signature(
        (child.text or "" for child in root if child.tag != "signature"),
        data["signature"],
    ):
        raise RegisterDealError("Invalid Paygine response signature")

    return data
