from __future__ import annotations

from api.config import BASE_SITE_LINK
from api.exceptions import PaymentInvalidProviderResponseError
from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_SECTOR, SR_REF
from api.payments.http_client import get_paygine_client
from api.payments.utils.commission_methods import calculate_payment_amounts, from_kopecks
from api.payments.utils.xml_response_parser import parse_paygine_response
from api.schemas.schemas_v1 import (
    DepositDealPaymentValues,
    RegisterDealCustomer,
    RegisterDealPaymentRequest,
    RegisterDepositDealPaymentRequest,
    RegisterDepositDealPaymentResponse,
    RegisterPayoutDealPaymentRequest,
)


REGISTER_DEAL_ENDPOINT = "/webapi/Register"
REGISTER_DEAL_SIGNATURE_FIELDS = ("sector", "amount", "currency")
PAYGINE_ORDER_STATUS_NOTIFY_PATH = "/v1/paygine/webhook_order_status"


async def create_deposit_deal(
    data: RegisterDepositDealPaymentRequest,
) -> RegisterDepositDealPaymentResponse:
    payment_data = build_deposit_deal_payment_request(data)
    provider_response = await create_registered_deal(payment_data)
    return RegisterDepositDealPaymentResponse(
        provider_response=provider_response,
        payment_values=build_deposit_order_payment_values(payment_data, provider_response),
    )


async def create_registered_deal(
    data: RegisterDealPaymentRequest,
) -> dict[str, object]:
    """Регистрируем сделку в ПЦ и возвращаем отформатированный ответ."""
    return await send_register_deal_request(data)


async def create_registered_payout_deal(
    data: RegisterPayoutDealPaymentRequest,
) -> dict[str, object]:
    """Регистрируем сделку вывода в ПЦ и возвращаем отформатированный ответ."""
    return await send_register_payout_deal_request(data)


def build_register_deal_payload(
    data: RegisterDealPaymentRequest,
) -> dict[str, object]:
    """Собираем form-urlencoded payload для webapi/Register."""
    payment_amounts = calculate_payment_amounts(data.amount)
    payload = {
        "sector": PAYGINE_SECTOR,
        "amount": payment_amounts["total_amount_with_fee"],
        "currency": data.currency,
        "sd_ref": SR_REF,
        "reference": data.reference,
        "description": data.description,
        "notify_url": data.notify_url,
        "payer_id": data.customer.client_ref,
        "email": data.customer.email,
        "phone": data.customer.phone,
    }
    payload["signature"] = build_signature(
        payload[field] for field in REGISTER_DEAL_SIGNATURE_FIELDS
    )
    return {key: value for key, value in payload.items() if value is not None}


def build_register_payout_deal_payload(
    data: RegisterPayoutDealPaymentRequest,
) -> dict[str, object]:
    """Собираем form-urlencoded payload для регистрации заказа вывода."""
    payment_amounts = calculate_payment_amounts(data.amount)
    payload = {
        "sector": PAYGINE_SECTOR,
        "amount": payment_amounts["order_amount"],
        "currency": data.currency,
        "sd_ref": SR_REF,
        "reference": data.reference,
        "description": data.description,
        "notify_url": data.notify_url,
        "client_ref": data.performer.client_ref,
        "email": data.performer.email,
        "phone": data.performer.phone,
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
    return parse_paygine_response(raw_response)


async def send_register_payout_deal_request(
    data: RegisterPayoutDealPaymentRequest,
) -> dict[str, object]:
    """Отправляем запрос регистрации заказа вывода в ПЦ Paygine."""
    payload = build_register_payout_deal_payload(data)
    raw_response = await post_register_deal(payload)
    return parse_paygine_response(raw_response)


async def post_register_deal(payload: dict[str, object]) -> str:
    """Выполняем асинхронный HTTP POST к webapi/Register."""
    client = get_paygine_client()
    response = await client.post(
        REGISTER_DEAL_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
    )
    response.raise_for_status()
    return response.text


def build_deposit_deal_payment_request(
    data: RegisterDepositDealPaymentRequest,
) -> RegisterDealPaymentRequest:
    return RegisterDealPaymentRequest(
        order_id=data.order_id,
        customer=RegisterDealCustomer(
            client_ref=str(data.client_id),
            email=data.customer_email,
            phone=data.customer_phone,
        ),
        amount=data.amount,
        expires_at=data.expires_at,
        reference=f"gladeal-order-{data.order_id}",
        description=data.description,
        notify_url=f"{BASE_SITE_LINK.rstrip('/')}{PAYGINE_ORDER_STATUS_NOTIFY_PATH}",
        currency=data.currency,
    )


def build_deposit_order_payment_values(
    payment_data: RegisterDealPaymentRequest,
    payment_response: dict[str, object],
) -> DepositDealPaymentValues:
    payment_amounts = calculate_payment_amounts(payment_data.amount)
    return DepositDealPaymentValues(
        currency=payment_data.currency,
        order_amount=from_kopecks(payment_amounts["order_amount"]),
        service_fee_amount=from_kopecks(payment_amounts["service_fee_amount"]),
        paygine_payment_operation_id=registered_deal_operation_id(payment_response),
        expires_at=payment_data.expires_at,
    )


def registered_deal_operation_id(response: dict[str, object]) -> str:
    data = response.get("data")
    if not isinstance(data, dict) or not data.get("id"):
        raise PaymentInvalidProviderResponseError(details=response)
    return str(data["id"])
