from api.payments.utils.register_deal_methods import create_registered_deal
from api.schemas.schemas_v1 import RegisterDealPaymentRequest


async def register_deal(
    payment_data: RegisterDealPaymentRequest,
) -> dict[str, object]:
    """Регистрируем платежную сделку в ПЦ и сохраняем ее платежные данные."""
    return await create_registered_deal(payment_data)


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
