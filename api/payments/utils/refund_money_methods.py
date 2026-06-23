from __future__ import annotations

from api.config import BASE_SITE_LINK
from api.payments.utils.register_deal_methods import (
    PAYGINE_ORDER_STATUS_NOTIFY_PATH,
    build_payout_order_payment_values,
    create_registered_payout_deal,
)
from api.schemas.schemas_v1 import (
    RegisterDealPerformer,
    RegisterPayoutDealPaymentResponse,
    RegisterPayoutDealProviderRequest,
    RefundMoneyPaymentRequest,
)


async def refund_registered_deal(
    data: RefundMoneyPaymentRequest,
) -> RegisterPayoutDealPaymentResponse:
    """Регистрируем возврат заказчику в ПЦ без сервисной комиссии."""
    refund_data = build_refund_money_payment_request(data)
    provider_response = await create_registered_payout_deal(refund_data)
    return RegisterPayoutDealPaymentResponse(
        provider_response=provider_response,
        payment_values=build_payout_order_payment_values(provider_response),
    )


def build_refund_money_payment_request(
    data: RefundMoneyPaymentRequest,
) -> RegisterPayoutDealProviderRequest:
    """Собираем provider-контракт возврата на client_ref заказчика."""
    return RegisterPayoutDealProviderRequest(
        order_id=data.order_id,
        performer=RegisterDealPerformer(
            client_ref=str(data.client_id),
            email=data.customer_email,
            phone=data.customer_phone,
        ),
        amount=data.amount,
        reference=f"gladeal-order-{data.order_id}-refund",
        description=data.description,
        notify_url=f"{BASE_SITE_LINK.rstrip('/')}{PAYGINE_ORDER_STATUS_NOTIFY_PATH}",
        currency=data.currency,
    )
