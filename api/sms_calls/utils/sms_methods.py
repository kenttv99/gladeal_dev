from __future__ import annotations

from api.sms_calls.config import (
    PROSTO_SMS_API_KEY,
    PROSTO_SMS_PRIORITY,
    PROSTO_SMS_SENDER_NAME,
)
from api.sms_calls.http_client import get_prosto_sms_client


PROSTO_SMS_METHOD = "push_msg"
PROSTO_SMS_FORMAT = "json"


def build_prosto_sms_payload(phone: int, code: str) -> dict[str, object]:
    """Собираем payload отправки SMS-кода через ProstoSMS."""
    return {
        "method": PROSTO_SMS_METHOD,
        "format": PROSTO_SMS_FORMAT,
        "key": PROSTO_SMS_API_KEY,
        "text": f"Код подтверждения: {code}",
        "phone": phone,
        "sender_name": PROSTO_SMS_SENDER_NAME,
        "priority": PROSTO_SMS_PRIORITY,
    }


async def send_prosto_sms_code(phone: int, code: str) -> dict[str, object]:
    """Отправляем SMS-код через ProstoSMS и возвращаем JSON-ответ провайдера."""
    client = get_prosto_sms_client()
    response = await client.post(
        "/",
        data=build_prosto_sms_payload(phone, code),
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
    )
    response.raise_for_status()
    return response.json()
