import httpx

from api.payments.config import PAYGINE_BASE_URL, PAYGINE_REQUEST_TIMEOUT_SECONDS


_paygine_client: httpx.AsyncClient | None = None


def get_paygine_client() -> httpx.AsyncClient:
    """Возвращаем общий асинхронный HTTP-клиент Paygine."""
    global _paygine_client
    if _paygine_client is None or _paygine_client.is_closed:
        _paygine_client = httpx.AsyncClient(
            base_url=PAYGINE_BASE_URL,
            timeout=PAYGINE_REQUEST_TIMEOUT_SECONDS,
            headers={"Accept": "*/*"},
        )
    return _paygine_client


async def close_paygine_client() -> None:
    """Закрываем общий асинхронный HTTP-клиент Paygine."""
    global _paygine_client
    if _paygine_client is not None and not _paygine_client.is_closed:
        await _paygine_client.aclose()
    _paygine_client = None
