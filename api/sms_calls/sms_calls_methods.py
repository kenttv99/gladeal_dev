from api.sms_calls.utils.calls_methods import send_prosto_call_code
from api.sms_calls.utils.code_generator import generate_verification_code
from api.sms_calls.utils.phone_methods import normalize_phone_to_int
from api.sms_calls.utils.sms_methods import send_prosto_sms_code
from api.sms_calls.utils.verification_code_storage_methods import (
    consume_phone_verified,
    consume_user_verified,
    delete_phone_verification_code,
    delete_user_verification_code,
    save_phone_verification_code,
    save_phone_verified,
    save_user_verification_code,
    save_user_verified,
    verify_phone_stored_code,
    verify_user_stored_code,
)


async def send_user_sms_code(user_id: int, phone: int | str, scope: str = "login") -> dict[str, object]:
    """Генерируем, привязываем к пользователю и отправляем SMS-код."""
    code = generate_verification_code()
    await save_user_verification_code(user_id, code, scope)
    try:
        provider_response = await send_prosto_sms_code(normalize_phone_to_int(phone), code)
    except Exception:
        await delete_user_verification_code(user_id, scope)
        raise
    return {"success": True, "provider_response": provider_response}


async def send_user_call_code(user_id: int, phone: int | str, scope: str = "login") -> dict[str, object]:
    """Генерируем, привязываем к пользователю и отправляем код через звонок."""
    code = generate_verification_code()
    await save_user_verification_code(user_id, code, scope)
    try:
        provider_response = await send_prosto_call_code(normalize_phone_to_int(phone), code)
    except Exception:
        await delete_user_verification_code(user_id, scope)
        raise
    return {"success": True, "provider_response": provider_response}


async def verify_user_sms_call_code(user_id: int, code: str, scope: str = "login") -> bool:
    """Проверяем введенный код пользователя и удаляем его при успешной проверке."""
    is_verified = await verify_user_stored_code(user_id, code, scope)
    if is_verified:
        await save_user_verified(user_id, scope)
    return is_verified


async def consume_user_sms_call_verification(user_id: int, scope: str = "login") -> bool:
    """Одноразово подтверждаем, что пользователь прошел проверку кода."""
    return await consume_user_verified(user_id, scope)


async def send_phone_sms_code(phone: int | str, scope: str = "register") -> dict[str, object]:
    """Генерируем, привязываем к телефону и отправляем SMS-код."""
    normalized_phone = normalize_phone_to_int(phone)
    code = generate_verification_code()
    await save_phone_verification_code(normalized_phone, code, scope)
    try:
        provider_response = await send_prosto_sms_code(normalized_phone, code)
    except Exception:
        await delete_phone_verification_code(normalized_phone, scope)
        raise
    return {"success": True, "verification_code_sent": True, "provider_response": provider_response}


async def send_phone_call_code(phone: int | str, scope: str = "register") -> dict[str, object]:
    """Генерируем, привязываем к телефону и отправляем код через звонок."""
    normalized_phone = normalize_phone_to_int(phone)
    code = generate_verification_code()
    await save_phone_verification_code(normalized_phone, code, scope)
    try:
        provider_response = await send_prosto_call_code(normalized_phone, code)
    except Exception:
        await delete_phone_verification_code(normalized_phone, scope)
        raise
    return {"success": True, "verification_code_sent": True, "provider_response": provider_response}


async def verify_phone_sms_call_code(phone: int | str, code: str, scope: str = "register") -> bool:
    """Проверяем введенный код телефона и удаляем его при успешной проверке."""
    normalized_phone = normalize_phone_to_int(phone)
    is_verified = await verify_phone_stored_code(normalized_phone, code, scope)
    if is_verified:
        await save_phone_verified(normalized_phone, scope)
    return is_verified


async def consume_phone_sms_call_verification(phone: int | str, scope: str = "register") -> bool:
    """Одноразово подтверждаем, что телефон прошел проверку кода."""
    return await consume_phone_verified(normalize_phone_to_int(phone), scope)
