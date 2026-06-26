import httpx

from api.sms_calls.config import PROSTO_SMS_BASE_URL, PROSTO_SMS_REQUEST_TIMEOUT_SECONDS


_prosto_sms_client: httpx.AsyncClient | None = None


def get_prosto_sms_client() -> httpx.AsyncClient:
    """Возвращаем общий асинхронный HTTP-клиент ProstoSMS."""
    global _prosto_sms_client
    if _prosto_sms_client is None or _prosto_sms_client.is_closed:
        _prosto_sms_client = httpx.AsyncClient(
            base_url=PROSTO_SMS_BASE_URL,
            timeout=PROSTO_SMS_REQUEST_TIMEOUT_SECONDS,
            headers={"Accept": "application/json"},
        )
    return _prosto_sms_client


async def close_prosto_sms_client() -> None:
    """Закрываем общий асинхронный HTTP-клиент ProstoSMS."""
    global _prosto_sms_client
    if _prosto_sms_client is not None and not _prosto_sms_client.is_closed:
        await _prosto_sms_client.aclose()
    _prosto_sms_client = None
