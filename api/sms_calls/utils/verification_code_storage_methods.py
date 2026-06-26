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


def build_user_verification_code_key(user_id: int) -> str:
    return f"sms_calls:verification_code:user:{user_id}"


async def save_user_verification_code(user_id: int, code: str) -> None:
    await get_sms_calls_redis().set(
        build_user_verification_code_key(user_id),
        code,
        ex=SMS_CALLS_CODE_TTL_SECONDS,
    )


async def delete_user_verification_code(user_id: int) -> None:
    await get_sms_calls_redis().delete(build_user_verification_code_key(user_id))


async def verify_user_stored_code(user_id: int, code: str) -> bool:
    result = await get_sms_calls_redis().eval(
        VERIFY_AND_DELETE_SCRIPT,
        1,
        build_user_verification_code_key(user_id),
        code,
    )
    return result == 1
