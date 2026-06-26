from api.sms_calls.utils.calls_methods import send_prosto_call_code
from api.sms_calls.utils.code_generator import generate_verification_code
from api.sms_calls.utils.phone_methods import normalize_phone_to_int
from api.sms_calls.utils.sms_methods import send_prosto_sms_code
from api.sms_calls.utils.verification_code_storage_methods import (
    delete_user_verification_code,
    save_user_verification_code,
    verify_user_stored_code,
)


async def send_user_sms_code(user_id: int, phone: int | str) -> dict[str, object]:
    """Генерируем, привязываем к пользователю и отправляем SMS-код."""
    code = generate_verification_code()
    await save_user_verification_code(user_id, code)
    try:
        provider_response = await send_prosto_sms_code(normalize_phone_to_int(phone), code)
    except Exception:
        await delete_user_verification_code(user_id)
        raise
    return {"success": True, "provider_response": provider_response}


async def send_user_call_code(user_id: int, phone: int | str) -> dict[str, object]:
    """Генерируем, привязываем к пользователю и отправляем код через звонок."""
    code = generate_verification_code()
    await save_user_verification_code(user_id, code)
    try:
        provider_response = await send_prosto_call_code(normalize_phone_to_int(phone), code)
    except Exception:
        await delete_user_verification_code(user_id)
        raise
    return {"success": True, "provider_response": provider_response}


async def verify_user_sms_call_code(user_id: int, code: str) -> bool:
    """Проверяем введенный код пользователя и удаляем его при успешной проверке."""
    return await verify_user_stored_code(user_id, code)
