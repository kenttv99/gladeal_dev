from __future__ import annotations

from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_SECTOR
from api.payments.http_client import get_paygine_client
from api.payments.utils.xml_response_parser import parse_paygine_response


REFUND_MONEY_ENDPOINT = "/webapi/b2puser/sd-services/SDReverse"
REFUND_MONEY_SIGNATURE_FIELDS = ("sector", "id")


async def refund_registered_deal(
    paygine_payment_operation_id: int,
) -> dict[str, object]:
    """Возвращаем средства заказчику в ПЦ и возвращаем отформатированный ответ."""
    payload = build_refund_money_payload(paygine_payment_operation_id)
    raw_response = await post_refund_money(payload)
    return parse_paygine_response(raw_response)


def build_refund_money_payload(
    paygine_payment_operation_id: int,
) -> dict[str, object]:
    """Собираем form-urlencoded payload для SDReverse."""
    payload = {
        "sector": PAYGINE_SECTOR,
        "id": paygine_payment_operation_id,
    }
    payload["signature"] = build_signature(
        payload[field] for field in REFUND_MONEY_SIGNATURE_FIELDS
    )
    return payload


async def post_refund_money(payload: dict[str, object]) -> str:
    """Выполняем асинхронный HTTP POST к SDReverse."""
    client = get_paygine_client()
    response = await client.post(
        REFUND_MONEY_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
    )
    response.raise_for_status()
    return response.text
