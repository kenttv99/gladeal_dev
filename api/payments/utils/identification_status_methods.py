from __future__ import annotations

from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_SECTOR
from api.payments.http_client import get_paygine_client
from api.payments.utils.xml_response_parser import parse_paygine_response


IDENTIFICATION_STATUS_ENDPOINT = "/webapi/p2pmarket/IdentificationStatus"
IDENTIFICATION_STATUS_SIGNATURE_FIELDS = (
    "sector",
    "first_name",
    "patronymic",
    "last_name",
    "birth_date",
    "persondoc_number",
)


def build_identification_status_payload(
    first_name: str,
    patronymic: str,
    last_name: str,
    birth_date: str,
    persondoc_number: str,
    mode: int = 1,
) -> dict[str, object]:
    """Собираем payload для вызова /webapi/p2pmarket/IdentificationStatus."""
    payload: dict[str, object] = {
        "mode": mode,
        "sector": PAYGINE_SECTOR,
        "first_name": first_name.strip()[:30],
        "patronymic": patronymic.strip()[:30],
        "last_name": last_name.strip()[:30],
        "birth_date": birth_date.strip()[:10],
        "persondoc_number": persondoc_number.strip()[:20],
    }
    payload["signature"] = build_signature(
        payload[field] for field in IDENTIFICATION_STATUS_SIGNATURE_FIELDS
    )
    return payload


async def post_identification_status(payload: dict[str, object]) -> str:
    """Выполняем асинхронный HTTP POST к эндпоинту IdentificationStatus."""
    client = get_paygine_client()
    response = await client.post(
        IDENTIFICATION_STATUS_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
    )
    response.raise_for_status()
    return response.text


async def request_identification_status(
    first_name: str,
    patronymic: str,
    last_name: str,
    birth_date: str,
    persondoc_number: str,
    mode: int = 1,
) -> dict[str, object]:
    """Отправляем запрос на проверку KYC в Paygine и возвращаем распарсенный XML-ответ."""
    payload = build_identification_status_payload(
        first_name=first_name,
        patronymic=patronymic,
        last_name=last_name,
        birth_date=birth_date,
        persondoc_number=persondoc_number,
        mode=mode,
    )
    raw_response = await post_identification_status(payload)
    return parse_paygine_response(raw_response)
