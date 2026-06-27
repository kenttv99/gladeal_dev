from __future__ import annotations

from api.sms_calls.http_client import get_prosto_sms_client
from api.sms_calls.utils.provider_response_methods import validate_prosto_sms_response
from api.sms_calls.utils.sms_methods import build_prosto_sms_payload





def build_prosto_call_payload(phone: int, code: str) -> dict[str, object]:
    """Собираем payload отправки кода через звонок ProstoSMS."""
    return {
        **build_prosto_sms_payload(phone, code),
        "route": "pc",
    }


async def send_prosto_call_code(phone: int, code: str) -> dict[str, object]:
    """Отправляем код через звонок ProstoSMS и возвращаем JSON-ответ провайдера."""
    client = get_prosto_sms_client()
    response = await client.post(
        "/",
        data=build_prosto_call_payload(phone, code),
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
    )
    response.raise_for_status()
    return validate_prosto_sms_response(response.json())
