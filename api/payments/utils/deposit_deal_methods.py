from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from api.config import BASE_SITE_LINK
from api.exceptions import PaymentInvalidProviderResponseError
from api.payments.utils.commission_methods import calculate_payment_amounts, from_kopecks
from api.payments.utils.phone_methods import normalize_paygine_phone
from api.payments.utils.register_deal_methods import create_registered_deal
from api.schemas.schemas_v1 import RegisterDealCustomer, RegisterDealPaymentRequest


PAYGINE_ORDER_STATUS_NOTIFY_PATH = "/v1/paygine/webhook_order_status"


@dataclass(frozen=True)
class DepositDealRegistrationResult:
    provider_response: dict[str, object]
    payment_values: dict[str, object]


async def create_deposit_deal(
    *,
    order_id: int,
    client_id: int,
    customer_email: str,
    customer_phone: str,
    amount: Decimal,
    expires_at: datetime,
    description: str,
    currency: int = 643,
) -> DepositDealRegistrationResult:
    payment_data = build_deposit_deal_payment_request(
        order_id=order_id,
        client_id=client_id,
        customer_email=customer_email,
        customer_phone=customer_phone,
        amount=amount,
        expires_at=expires_at,
        description=description,
        currency=currency,
    )
    provider_response = await create_registered_deal(payment_data)
    return DepositDealRegistrationResult(
        provider_response=provider_response,
        payment_values=build_deposit_order_payment_values(payment_data, provider_response),
    )


def build_deposit_deal_payment_request(
    *,
    order_id: int,
    client_id: int,
    customer_email: str,
    customer_phone: str,
    amount: Decimal,
    expires_at: datetime,
    description: str,
    currency: int = 643,
) -> RegisterDealPaymentRequest:
    return RegisterDealPaymentRequest(
        order_id=order_id,
        customer=RegisterDealCustomer(
            client_ref=str(client_id),
            email=customer_email,
            phone=normalize_paygine_phone(customer_phone),
        ),
        amount=amount,
        expires_at=expires_at,
        reference=f"gladeal-order-{order_id}",
        description=description,
        notify_url=f"{BASE_SITE_LINK.rstrip('/')}{PAYGINE_ORDER_STATUS_NOTIFY_PATH}",
        currency=currency,
    )


def build_deposit_order_payment_values(
    payment_data: RegisterDealPaymentRequest,
    payment_response: dict[str, object],
) -> dict[str, object]:
    payment_amounts = calculate_payment_amounts(payment_data.amount)
    return {
        "currency": payment_data.currency,
        "order_amount": from_kopecks(payment_amounts["order_amount"]),
        "service_fee_amount": from_kopecks(payment_amounts["service_fee_amount"]),
        "paygine_payment_operation_id": registered_deal_operation_id(payment_response),
        "expires_at": payment_data.expires_at,
    }


def registered_deal_operation_id(response: dict[str, object]) -> str:
    data = response.get("data")
    if not isinstance(data, dict) or not data.get("id"):
        raise PaymentInvalidProviderResponseError(details=response)
    return str(data["id"])
