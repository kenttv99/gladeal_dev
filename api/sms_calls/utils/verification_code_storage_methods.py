from __future__ import annotations

from api.exceptions import SmsCallsRateLimitError
from api.sms_calls.config import (
    SMS_CALLS_CODE_TTL_SECONDS,
    SMS_CALLS_SEND_ATTEMPTS_LIMIT,
    SMS_CALLS_SEND_LIMIT_PAUSE_SECONDS,
    SMS_CALLS_VERIFY_ATTEMPTS_LIMIT,
)
from api.sms_calls.redis_client import get_sms_calls_redis


VERIFY_AND_DELETE_SCRIPT = """
local code = redis.call("GET", KEYS[1])
if not code then
    return 0
end
if code ~= ARGV[1] then
    local attempts = redis.call("INCR", KEYS[2])
    if attempts == 1 then
        redis.call("EXPIRE", KEYS[2], ARGV[3])
    end
    if attempts >= tonumber(ARGV[2]) then
        redis.call("DEL", KEYS[1])
        redis.call("DEL", KEYS[2])
    end
    return 0
end
redis.call("DEL", KEYS[1])
redis.call("DEL", KEYS[2])
return 1
"""


RESERVE_SEND_ATTEMPT_SCRIPT = """
local attempts = redis.call("INCR", KEYS[1])
if attempts == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[2])
end
if attempts > tonumber(ARGV[1]) then
    return 0
end
return 1
"""


RELEASE_SEND_ATTEMPT_SCRIPT = """
local attempts = redis.call("DECR", KEYS[1])
if attempts <= 0 then
    redis.call("DEL", KEYS[1])
end
return attempts
"""


CONSUME_VERIFIED_SCRIPT = """
local verified = redis.call("GET", KEYS[1])
if not verified then
    return 0
end
redis.call("DEL", KEYS[1])
return 1
"""


def build_user_verification_code_key(user_id: int, scope: str = "login") -> str:
    return f"sms_calls:verification_code:{scope}:user:{user_id}"


def build_user_verification_attempts_key(user_id: int, scope: str = "login") -> str:
    return f"sms_calls:verification_attempts:{scope}:user:{user_id}"


def build_user_send_attempts_key(user_id: int, scope: str = "login") -> str:
    return f"sms_calls:send_attempts:{scope}:user:{user_id}"


def build_user_verified_key(user_id: int, scope: str = "login") -> str:
    return f"sms_calls:verified:{scope}:user:{user_id}"


def build_phone_verification_code_key(phone: int, scope: str = "register") -> str:
    return f"sms_calls:verification_code:{scope}:phone:{phone}"


def build_phone_verification_attempts_key(phone: int, scope: str = "register") -> str:
    return f"sms_calls:verification_attempts:{scope}:phone:{phone}"


def build_phone_send_attempts_key(phone: int, scope: str = "register") -> str:
    return f"sms_calls:send_attempts:{scope}:phone:{phone}"


def build_phone_verified_key(phone: int, scope: str = "register") -> str:
    return f"sms_calls:verified:{scope}:phone:{phone}"


async def save_verification_code(key: str, attempts_key: str, code: str) -> None:
    redis = get_sms_calls_redis()
    await redis.set(key, code, ex=SMS_CALLS_CODE_TTL_SECONDS)
    await redis.delete(attempts_key)


async def delete_verification_code(key: str, attempts_key: str) -> None:
    await get_sms_calls_redis().delete(key, attempts_key)


async def reserve_send_attempt(key: str) -> None:
    result = await get_sms_calls_redis().eval(
        RESERVE_SEND_ATTEMPT_SCRIPT,
        1,
        key,
        SMS_CALLS_SEND_ATTEMPTS_LIMIT,
        SMS_CALLS_SEND_LIMIT_PAUSE_SECONDS,
    )
    if result != 1:
        raise SmsCallsRateLimitError()


async def release_send_attempt(key: str) -> None:
    await get_sms_calls_redis().eval(RELEASE_SEND_ATTEMPT_SCRIPT, 1, key)


async def verify_stored_code(key: str, attempts_key: str, code: str) -> bool:
    result = await get_sms_calls_redis().eval(
        VERIFY_AND_DELETE_SCRIPT,
        2,
        key,
        attempts_key,
        code,
        SMS_CALLS_VERIFY_ATTEMPTS_LIMIT,
        SMS_CALLS_CODE_TTL_SECONDS,
    )
    return result == 1


async def save_verified(key: str) -> None:
    await get_sms_calls_redis().set(key, "1", ex=SMS_CALLS_CODE_TTL_SECONDS)


async def consume_verified(key: str) -> bool:
    result = await get_sms_calls_redis().eval(CONSUME_VERIFIED_SCRIPT, 1, key)
    return result == 1


async def save_user_verification_code(user_id: int, code: str, scope: str = "login") -> None:
    await save_verification_code(
        build_user_verification_code_key(user_id, scope),
        build_user_verification_attempts_key(user_id, scope),
        code,
    )


async def delete_user_verification_code(user_id: int, scope: str = "login") -> None:
    await delete_verification_code(
        build_user_verification_code_key(user_id, scope),
        build_user_verification_attempts_key(user_id, scope),
    )


async def verify_user_stored_code(user_id: int, code: str, scope: str = "login") -> bool:
    return await verify_stored_code(
        build_user_verification_code_key(user_id, scope),
        build_user_verification_attempts_key(user_id, scope),
        code,
    )


async def reserve_user_code_send(user_id: int, scope: str = "login") -> None:
    await reserve_send_attempt(build_user_send_attempts_key(user_id, scope))


async def release_user_code_send(user_id: int, scope: str = "login") -> None:
    await release_send_attempt(build_user_send_attempts_key(user_id, scope))


async def save_user_verified(user_id: int, scope: str = "login") -> None:
    await save_verified(build_user_verified_key(user_id, scope))


async def consume_user_verified(user_id: int, scope: str = "login") -> bool:
    return await consume_verified(build_user_verified_key(user_id, scope))


async def save_phone_verification_code(phone: int, code: str, scope: str = "register") -> None:
    await save_verification_code(
        build_phone_verification_code_key(phone, scope),
        build_phone_verification_attempts_key(phone, scope),
        code,
    )


async def delete_phone_verification_code(phone: int, scope: str = "register") -> None:
    await delete_verification_code(
        build_phone_verification_code_key(phone, scope),
        build_phone_verification_attempts_key(phone, scope),
    )


async def verify_phone_stored_code(phone: int, code: str, scope: str = "register") -> bool:
    return await verify_stored_code(
        build_phone_verification_code_key(phone, scope),
        build_phone_verification_attempts_key(phone, scope),
        code,
    )


async def reserve_phone_code_send(phone: int, scope: str = "register") -> None:
    await reserve_send_attempt(build_phone_send_attempts_key(phone, scope))


async def release_phone_code_send(phone: int, scope: str = "register") -> None:
    await release_send_attempt(build_phone_send_attempts_key(phone, scope))


async def save_phone_verified(phone: int, scope: str = "register") -> None:
    await save_verified(build_phone_verified_key(phone, scope))


async def consume_phone_verified(phone: int, scope: str = "register") -> bool:
    return await consume_verified(build_phone_verified_key(phone, scope))
