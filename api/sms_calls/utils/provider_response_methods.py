from __future__ import annotations

from api.exceptions import SmsCallsProviderError


def validate_prosto_sms_response(response: dict[str, object]) -> dict[str, object]:
    """Проверяем JSON-ответ ProstoSMS на бизнес-ошибку провайдера."""
    provider_response = response.get("response")
    if not isinstance(provider_response, dict):
        return response

    message = provider_response.get("msg")
    if not isinstance(message, dict):
        return response

    error_code = message.get("err_code")
    message_type = message.get("type")
    if message_type == "error" or error_code not in (None, "", "0", 0):
        raise SmsCallsProviderError(details=response)

    return response
