from __future__ import annotations

from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_SECTOR
from api.payments.http_client import get_paygine_client
from api.payments.utils.xml_response_parser import parse_paygine_response
from api.schemas.schemas_v1 import CancleUnpaymentDealRequest


CHANGE_ORDER_STATUS_ENDPOINT = "/webapi/ChangeOrderStatus"
EXPIRED_ORDER_STATE = "EXPIRED"
CHANGE_ORDER_STATUS_SIGNATURE_FIELDS = ("sector", "id", "order_state")


async def cancle_registered_deal(
    data: CancleUnpaymentDealRequest,
) -> dict[str, object]:
    """Переводим неоплаченную сделку в статус EXPIRED в ПЦ."""
    payload = build_cancle_unpayment_deal_payload(data)
    raw_response = await post_cancle_unpayment_deal(payload)
    return parse_paygine_response(raw_response)


def build_cancle_unpayment_deal_payload(
    data: CancleUnpaymentDealRequest,
) -> dict[str, object]:
    """Собираем form-urlencoded payload для webapi/ChangeOrderStatus."""
    payload = {
        "sector": PAYGINE_SECTOR,
        "id": data.paygine_payment_operation_id,
        "order_state": EXPIRED_ORDER_STATE,
    }
    payload["signature"] = build_signature(
        payload[field] for field in CHANGE_ORDER_STATUS_SIGNATURE_FIELDS
    )
    return payload


async def post_cancle_unpayment_deal(payload: dict[str, object]) -> str:
    """Выполняем асинхронный HTTP POST к webapi/ChangeOrderStatus."""
    client = get_paygine_client()
    response = await client.post(
        CHANGE_ORDER_STATUS_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
    )
    response.raise_for_status()
    return response.text
