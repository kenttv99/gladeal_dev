from api.payments.utils.cancle_unpayment_deal_methods import cancle_registered_deal
from api.payments.utils.complete_paymented_deal_methods import complete_registered_deal
from api.payments.utils.generate_payment_link_methods import create_payment_link
from api.payments.utils.generate_withdrow_link_methods import create_withdrow_link
from api.payments.utils.register_deal_methods import (
    create_deposit_deal,
    create_registered_payout_deal,
)
from api.payments.utils.refund_money_methods import refund_registered_deal
from api.schemas.schemas_v1 import (
    CancleUnpaymentDealRequest,
    CompletePaymentedDealRequest,
    GeneratePaymentLinkRequest,
    GenerateWithdrowLinkRequest,
    RegisterDepositDealPaymentRequest,
    RegisterDepositDealPaymentResponse,
    RegisterPayoutDealPaymentRequest,
    RefundMoneyRequest,
)


async def register_deposit_deal(
    payment_data: RegisterDepositDealPaymentRequest,
) -> RegisterDepositDealPaymentResponse:
    """Регистрируем платежную сделку в ПЦ для депозита и возвращаем ответ провайдера"""
    return await create_deposit_deal(payment_data)

async def register_payout_deal(
    payment_data: RegisterPayoutDealPaymentRequest,
) -> dict[str, object]:
    """Регистрируем сделку в ПЦ для вывода и возвращаем ответ провайдера"""
    return await create_registered_payout_deal(payment_data)


async def cancle_unpayment_deal(
    payment_data: CancleUnpaymentDealRequest,
) -> dict[str, object]:
    """Переводим неоплаченную платежную сделку в статус EXPIRED."""
    return await cancle_registered_deal(payment_data)


async def generate_payment_link(
    payment_data: GeneratePaymentLinkRequest,
) -> str:
    """Генерируем ссылку для оплаты + заморозки средств"""
    return await create_payment_link(payment_data)


async def generate_withdrow_link(
    payment_data: GenerateWithdrowLinkRequest,
) -> str:
    """Генерируем ссылку для получения средств исполнителем"""
    return await create_withdrow_link(payment_data)


async def complete_paymented_deal(
    payment_data: CompletePaymentedDealRequest,
) -> dict[str, object]:
    """Завершаем оплаченную сделку в ПЦ."""
    return await complete_registered_deal(payment_data)


async def refund_money(
    payment_data: RefundMoneyRequest,
) -> dict[str, object]:
    """Возвращаем средства заказчику после заморозки."""
    return await refund_registered_deal(payment_data)
