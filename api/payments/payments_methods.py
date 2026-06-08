from api.payments.utils.cancle_unpayment_deal_methods import cancle_registered_deal
from api.payments.utils.generate_payment_link_methods import create_payment_link
from api.payments.utils.generate_withdrow_link_methods import create_withdrow_link
from api.payments.utils.register_deal_methods import create_registered_deal
from api.schemas.schemas_v1 import (
    CancleUnpaymentDealRequest,
    GeneratePaymentLinkRequest,
    GenerateWithdrowLinkRequest,
    RegisterDealPaymentRequest,
)


async def register_deal(
    payment_data: RegisterDealPaymentRequest,
) -> dict[str, object]:
    """Регистрируем платежную сделку в ПЦ и возвращаем ответ провайдера + замораживаем средства при оплате со стороны пользвоателя"""
    return await create_registered_deal(payment_data)


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

async def refund_money() -> None:
    """Возвращаем средства заказчику."""
    pass

async def calculate_commissions() -> None:
    """Рассчитываем комиссии платежной сделки."""
    pass

async def status_handle() -> None:
    """Обрабатываем статус платежной операции."""
    pass
