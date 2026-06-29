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


async def _send_code(
    target: int,
    scope: str,
    save_code,
    delete_code,
    send_code,
    include_sent_flag: bool,
) -> dict[str, object]:
    code = generate_verification_code()
    await save_code(target, code, scope)
    try:
        provider_response = await send_code(target, code)
    except Exception:
        await delete_code(target, scope)
        raise
    response = {"success": True, "provider_response": provider_response}
    if include_sent_flag:
        response["verification_code_sent"] = True
    return response


async def _verify_code(
    target: int,
    code: str,
    scope: str,
    verify_code,
    save_verified,
) -> bool:
    is_verified = await verify_code(target, code, scope)
    if is_verified:
        await save_verified(target, scope)
    return is_verified


async def send_user_sms_code(user_id: int, phone: int | str, scope: str = "login") -> dict[str, object]:
    """Генерируем, привязываем к пользователю и отправляем SMS-код."""
    return await _send_code(
        user_id,
        scope,
        save_user_verification_code,
        delete_user_verification_code,
        lambda _, code: send_prosto_sms_code(normalize_phone_to_int(phone), code),
        False,
    )


async def send_user_call_code(user_id: int, phone: int | str, scope: str = "login") -> dict[str, object]:
    """Генерируем, привязываем к пользователю и отправляем код через звонок."""
    return await _send_code(
        user_id,
        scope,
        save_user_verification_code,
        delete_user_verification_code,
        lambda _, code: send_prosto_call_code(normalize_phone_to_int(phone), code),
        False,
    )


async def verify_user_sms_call_code(user_id: int, code: str, scope: str = "login") -> bool:
    """Проверяем введенный код пользователя и удаляем его при успешной проверке."""
    return await _verify_code(user_id, code, scope, verify_user_stored_code, save_user_verified)


async def consume_user_sms_call_verification(user_id: int, scope: str = "login") -> bool:
    """Одноразово подтверждаем, что пользователь прошел проверку кода."""
    return await consume_user_verified(user_id, scope)


async def send_phone_sms_code(phone: int | str, scope: str = "register") -> dict[str, object]:
    """Генерируем, привязываем к телефону и отправляем SMS-код."""
    normalized_phone = normalize_phone_to_int(phone)
    return await _send_code(
        normalized_phone,
        scope,
        save_phone_verification_code,
        delete_phone_verification_code,
        send_prosto_sms_code,
        True,
    )


async def send_phone_call_code(phone: int | str, scope: str = "register") -> dict[str, object]:
    """Генерируем, привязываем к телефону и отправляем код через звонок."""
    normalized_phone = normalize_phone_to_int(phone)
    return await _send_code(
        normalized_phone,
        scope,
        save_phone_verification_code,
        delete_phone_verification_code,
        send_prosto_call_code,
        True,
    )


async def verify_phone_sms_call_code(phone: int | str, code: str, scope: str = "register") -> bool:
    """Проверяем введенный код телефона и удаляем его при успешной проверке."""
    return await _verify_code(
        normalize_phone_to_int(phone),
        code,
        scope,
        verify_phone_stored_code,
        save_phone_verified,
    )


async def consume_phone_sms_call_verification(phone: int | str, scope: str = "register") -> bool:
    """Одноразово подтверждаем, что телефон прошел проверку кода."""
    return await consume_phone_verified(normalize_phone_to_int(phone), scope)
