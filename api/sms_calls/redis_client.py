from redis.asyncio import Redis

from api.sms_calls.config import SMS_CALLS_REDIS_URL


_sms_calls_redis: Redis | None = None


def get_sms_calls_redis() -> Redis:
    """Возвращаем общий Redis-клиент для кодов подтверждения."""
    global _sms_calls_redis
    if _sms_calls_redis is None:
        _sms_calls_redis = Redis.from_url(SMS_CALLS_REDIS_URL, decode_responses=True)
    return _sms_calls_redis


async def close_sms_calls_redis() -> None:
    """Закрываем общий Redis-клиент кодов подтверждения."""
    global _sms_calls_redis
    if _sms_calls_redis is not None:
        await _sms_calls_redis.aclose()
    _sms_calls_redis = None
