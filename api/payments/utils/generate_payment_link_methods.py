from __future__ import annotations

from urllib.parse import urlencode

from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_BASE_URL, PAYGINE_SECTOR, SR_REF
from api.schemas.schemas_v1 import GeneratePaymentLinkRequest


GENERATE_PAYMENT_LINK_ENDPOINT = "/webapi/b2puser/sd-services/SDPayInDebit"
GENERATE_PAYMENT_LINK_SIGNATURE_FIELDS = ("sector", "id", "sd_ref")


async def create_payment_link(
    data: GeneratePaymentLinkRequest,
) -> str:
    """Генерируем ссылку для оплаты и заморозки средств."""
    payload = build_generate_payment_link_payload(data)
    query = urlencode(payload)
    return f"{PAYGINE_BASE_URL.rstrip('/')}{GENERATE_PAYMENT_LINK_ENDPOINT}?{query}"


def build_generate_payment_link_payload(
    data: GeneratePaymentLinkRequest,
) -> dict[str, object]:
    """Собираем query params для SDPayInDebit."""
    payload = {
        "sector": PAYGINE_SECTOR,
        "id": data.paygine_payment_operation_id,
        "sd_ref": SR_REF,
    }
    payload["signature"] = build_signature(
        payload[field] for field in GENERATE_PAYMENT_LINK_SIGNATURE_FIELDS
    )
    return payload
