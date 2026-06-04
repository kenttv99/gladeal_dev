from api.payments.utils.register_deal_methods import create_registered_deal
from api.schemas.schemas_v1 import RegisterDealPaymentRequest, RegisterDealPaymentResponse


async def register_deal(
    payment_data: RegisterDealPaymentRequest,
) -> RegisterDealPaymentResponse:
    """Регистрирует платежную сделку в ПЦ и сохраняет ее платежные данные."""
    return await create_registered_deal(payment_data)


async def freeze_money() -> None:
    """Замораживает средства заказчика в ПЦ."""
    pass


async def withdraw_to_performer() -> None:
    """Создает выплату средств исполнителю."""
    pass


async def refund_money() -> None:
    """Возвращает средства заказчику."""
    pass


async def revoke_deal() -> None:
    """Отзывает платежную сделку."""
    pass


async def calculate_commissions() -> None:
    """Рассчитывает комиссии платежной сделки."""
    pass


async def status_handle() -> None:
    """Обрабатывает статус платежной операции."""
    pass
