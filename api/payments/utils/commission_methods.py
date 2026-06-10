from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

from api.payments.config import DEAL_FEE_PERCENT


KOPECKS_IN_RUBLE = Decimal("100")
KOPECK_AMOUNT_STEP = Decimal("1")


def to_kopecks(amount: Decimal) -> int:
    return int((amount * KOPECKS_IN_RUBLE).quantize(KOPECK_AMOUNT_STEP, ROUND_DOWN))


def calculate_payment_amounts(order_amount: Decimal) -> dict[str, int]:
    """Считаем суммы в рублях и возвращаем целые копейки для Paygine."""
    service_fee_amount = order_amount * DEAL_FEE_PERCENT / Decimal("100")
    total_amount_with_fee = order_amount + service_fee_amount
    return {
        "total_amount_with_fee": to_kopecks(total_amount_with_fee),
        "order_amount": to_kopecks(order_amount),
        "service_fee_amount": to_kopecks(service_fee_amount),
    }
