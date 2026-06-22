from __future__ import annotations

from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_SECTOR, SR_REF
from api.payments.http_client import get_paygine_client
from api.payments.utils.xml_response_parser import parse_paygine_response


SD_GET_BALANCE_ENDPOINT = "/webapi/b2puser/sd-services/SDGetBalance"
SD_GET_BALANCE_SIGNATURE_FIELDS = ("sector", "sd_ref")


def build_sd_get_balance_payload() -> dict[str, object]:
    """Собираем form-urlencoded payload для получения баланса кубышки."""
    payload = {
        "sector": PAYGINE_SECTOR,
        "sd_ref": SR_REF,
    }
    payload["signature"] = build_signature(
        payload[field] for field in SD_GET_BALANCE_SIGNATURE_FIELDS
    )
    return payload


async def get_sd_balance() -> dict[str, object]:
    """Получаем баланс кубышки в ПЦ Paygine."""
    client = get_paygine_client()
    response = await client.post(
        SD_GET_BALANCE_ENDPOINT,
        data=build_sd_get_balance_payload(),
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
    )
    response.raise_for_status()
    return parse_paygine_response(response.text)
