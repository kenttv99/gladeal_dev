from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

from api.payments.config import DEAL_FEE_PERCENT


DECIMAL_AMOUNT_STEP = Decimal("0.01")


def calculate_payment_amounts(order_amount: Decimal | int) -> dict[str, Decimal]:
    """Возвращаем сумму с комиссией, сумму сделки и комиссию с точностью до 0.01."""
    amount = Decimal(order_amount).quantize(DECIMAL_AMOUNT_STEP, rounding=ROUND_DOWN)
    service_fee_amount = (
        amount * DEAL_FEE_PERCENT / Decimal("100")
    ).quantize(
        DECIMAL_AMOUNT_STEP,
        rounding=ROUND_DOWN,
    )
    return {
        "total_amount_with_fee": amount + service_fee_amount,
        "order_amount": amount,
        "service_fee_amount": service_fee_amount,
    }
