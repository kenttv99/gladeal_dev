from api.sms_calls.utils.calls_methods import send_prosto_call_code
from api.sms_calls.utils.code_generator import generate_verification_code
from api.sms_calls.utils.sms_methods import send_prosto_sms_code


async def send_sms_code(phone: int) -> dict[str, object]:
    """Генерируем и отправляем SMS-код подтверждения."""
    code = generate_verification_code()
    return {
        "code": code,
        "provider_response": await send_prosto_sms_code(phone, code),
    }


async def send_call_code(phone: int) -> dict[str, object]:
    """Генерируем и отправляем код подтверждения через звонок."""
    code = generate_verification_code()
    return {
        "code": code,
        "provider_response": await send_prosto_call_code(phone, code),
    }
