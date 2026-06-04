from api.payments.utils.cancle_unpayment_deal_methods import cancle_registered_deal
from api.payments.utils.register_deal_methods import create_registered_deal
from api.schemas.schemas_v1 import (
    CancleUnpaymentDealRequest,
    RegisterDealPaymentRequest,
)


async def register_deal(
    payment_data: RegisterDealPaymentRequest,
) -> dict[str, object]:
    """Регистрируем платежную сделку в ПЦ и возвращаем ответ провайдера."""
    return await create_registered_deal(payment_data)


async def cancle_unpayment_deal(
    payment_data: CancleUnpaymentDealRequest,
) -> dict[str, object]:
    """Переводим неоплаченную платежную сделку в статус EXPIRED."""
    return await cancle_registered_deal(payment_data)


async def freeze_money() -> None:
    """Замораживаем средства заказчика в ПЦ."""
    pass


async def withdraw_to_performer() -> None:
    """Создаем выплату средств исполнителю."""
    pass


async def refund_money() -> None:
    """Возвращаем средства заказчику."""
    pass


async def revoke_deal() -> None:
    """Отзываем платежную сделку."""
    pass


async def calculate_commissions() -> None:
    """Рассчитываем комиссии платежной сделки."""
    pass


async def status_handle() -> None:
    """Обрабатываем статус платежной операции."""
    pass
