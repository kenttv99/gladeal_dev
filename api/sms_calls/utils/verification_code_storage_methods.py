from __future__ import annotations

from api.sms_calls.config import SMS_CALLS_CODE_TTL_SECONDS
from api.sms_calls.redis_client import get_sms_calls_redis


VERIFY_AND_DELETE_SCRIPT = """
local code = redis.call("GET", KEYS[1])
if not code or code ~= ARGV[1] then
    return 0
end
redis.call("DEL", KEYS[1])
return 1
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


def build_user_verified_key(user_id: int, scope: str = "login") -> str:
    return f"sms_calls:verified:{scope}:user:{user_id}"


def build_phone_verification_code_key(phone: int, scope: str = "register") -> str:
    return f"sms_calls:verification_code:{scope}:phone:{phone}"


def build_phone_verified_key(phone: int, scope: str = "register") -> str:
    return f"sms_calls:verified:{scope}:phone:{phone}"


async def save_verification_code(key: str, code: str) -> None:
    await get_sms_calls_redis().set(key, code, ex=SMS_CALLS_CODE_TTL_SECONDS)


async def delete_verification_code(key: str) -> None:
    await get_sms_calls_redis().delete(key)


async def verify_stored_code(key: str, code: str) -> bool:
    result = await get_sms_calls_redis().eval(VERIFY_AND_DELETE_SCRIPT, 1, key, code)
    return result == 1


async def save_verified(key: str) -> None:
    await get_sms_calls_redis().set(key, "1", ex=SMS_CALLS_CODE_TTL_SECONDS)


async def consume_verified(key: str) -> bool:
    result = await get_sms_calls_redis().eval(CONSUME_VERIFIED_SCRIPT, 1, key)
    return result == 1


async def save_user_verification_code(user_id: int, code: str, scope: str = "login") -> None:
    await save_verification_code(build_user_verification_code_key(user_id, scope), code)


async def delete_user_verification_code(user_id: int, scope: str = "login") -> None:
    await delete_verification_code(build_user_verification_code_key(user_id, scope))


async def verify_user_stored_code(user_id: int, code: str, scope: str = "login") -> bool:
    return await verify_stored_code(build_user_verification_code_key(user_id, scope), code)


async def save_user_verified(user_id: int, scope: str = "login") -> None:
    await save_verified(build_user_verified_key(user_id, scope))


async def consume_user_verified(user_id: int, scope: str = "login") -> bool:
    return await consume_verified(build_user_verified_key(user_id, scope))


async def save_phone_verification_code(phone: int, code: str, scope: str = "register") -> None:
    await save_verification_code(build_phone_verification_code_key(phone, scope), code)


async def delete_phone_verification_code(phone: int, scope: str = "register") -> None:
    await delete_verification_code(build_phone_verification_code_key(phone, scope))


async def verify_phone_stored_code(phone: int, code: str, scope: str = "register") -> bool:
    return await verify_stored_code(build_phone_verification_code_key(phone, scope), code)


async def save_phone_verified(phone: int, scope: str = "register") -> None:
    await save_verified(build_phone_verified_key(phone, scope))


async def consume_phone_verified(phone: int, scope: str = "register") -> bool:
    return await consume_verified(build_phone_verified_key(phone, scope))
