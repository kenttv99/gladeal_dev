from fastapi import APIRouter, Body, Depends

from api.enums.enums_v1 import VerificationMethods, VerificationScopes
from api.schemas.schemas_v1 import (
    AccessTokenRefreshResponse,
    AuthUserResponse,
    LoginUserRequest,
    PhoneVerificationCodeRequest,
    PhoneVerificationCodeVerifyRequest,
    RegisterUserRequest,
    ResetPhoneNumberRequest,
)
from api.sms_calls.sms_calls_methods import (
    consume_phone_sms_call_verification,
    consume_user_sms_call_verification,
    send_phone_call_code,
    send_phone_sms_code,
    send_user_call_code,
    send_user_sms_code,
    verify_phone_sms_call_code,
    verify_user_sms_call_code,
)
from api.utils.jwt_methods import (
    authorize_user,
    create_refresh_token,
    generate_access_token,
    refresh_access_token,
    revoke_refresh_token,
)
from api.utils.users_methods import (
    authenticate_user,
    delete_account as delete_account_method,
    ensure_phone_number_available,
    register_user,
    reset_phone_number as reset_phone_number_method,
)


router = APIRouter()


RESET_PHONE_NUMBER_VERIFICATION_SCOPE = VerificationScopes.RESET_PHONE_NUMBER.value


@router.post("/register")
async def register(user: RegisterUserRequest):
    if not await consume_phone_sms_call_verification(
        user.phone_number,
        VerificationScopes.REGISTER.value,
    ):
        return {"success": False}

    return await register_user(
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=user.phone_number,
        ppd=user.ppd,
    )

@router.post("/register/without_sms")
async def register_without_sms(user: RegisterUserRequest):
    '''Запасной ендпоинт для регистрации без смс'''
    return await register_user(
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=user.phone_number,
        ppd=user.ppd,
    )


@router.post("/delete-account")
async def delete_account(
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    await delete_account_method(authorized_user_id)
    return {"success": True}


@router.post("/login")
async def auth(data: LoginUserRequest) -> AuthUserResponse | dict[str, bool]:
    user_id = await authenticate_user(data.phone_number)
    if not await consume_user_sms_call_verification(user_id, VerificationScopes.LOGIN.value):
        return {"success": False}

    refresh_token, refresh_token_expires_at = await create_refresh_token(user_id)
    return AuthUserResponse(
        access_token=generate_access_token(user_id),
        refresh_token=refresh_token,
        refresh_token_expires_at=refresh_token_expires_at,
    )

@router.post("/login/without_sms")
async def auth_without_sms(data: LoginUserRequest) -> AuthUserResponse | dict[str, bool]:
    '''Запасной ендпоинт для авторизации без смс'''
    user_id = await authenticate_user(data.phone_number)
    refresh_token, refresh_token_expires_at = await create_refresh_token(user_id)
    return AuthUserResponse(
        access_token=generate_access_token(user_id),
        refresh_token=refresh_token,
        refresh_token_expires_at=refresh_token_expires_at,
    )


@router.post("/access_token_refresh/")
async def access_token_refresh(
    refresh_token: str = Body(..., embed=True),
) -> AccessTokenRefreshResponse:
    return AccessTokenRefreshResponse(
        access_token=await refresh_access_token(refresh_token)
    )


@router.post("/logout/")
async def logout(
    refresh_token: str = Body(..., embed=True),
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    await revoke_refresh_token(authorized_user_id, refresh_token)
    return {"success": True}


@router.post("/reset-phone-number")
async def reset_phone_number(
    data: ResetPhoneNumberRequest,
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    await ensure_phone_number_available(data.phone_number, authorized_user_id)
    if not await consume_phone_sms_call_verification(
        data.phone_number,
        RESET_PHONE_NUMBER_VERIFICATION_SCOPE,
    ):
        return {"success": False}

    await reset_phone_number_method(authorized_user_id, data.phone_number)
    return {"success": True}

@router.post("/reset-phone-number/without_sms")
async def reset_phone_number(
    data: ResetPhoneNumberRequest,
    authorized_user_id: int = Depends(authorize_user),
) -> dict[str, bool]:
    '''Запасной ендпоинт для смены номера телефона'''
    await reset_phone_number_method(authorized_user_id, data.phone_number)
    return {"success": True}


@router.post("/verification-code")
async def send_verification_code(
    data: PhoneVerificationCodeRequest,
) -> dict[str, object]:
    if data.verification_scope == VerificationScopes.LOGIN:
        user_id = await authenticate_user(data.phone_number)
        if data.verification_method == VerificationMethods.CALL:
            return await send_user_call_code(user_id, data.phone_number, VerificationScopes.LOGIN.value)
        return await send_user_sms_code(user_id, data.phone_number, VerificationScopes.LOGIN.value)

    if data.verification_scope == VerificationScopes.REGISTER:
        await ensure_phone_number_available(data.phone_number)
        if data.verification_method == VerificationMethods.CALL:
            return await send_phone_call_code(data.phone_number, VerificationScopes.REGISTER.value)
        return await send_phone_sms_code(data.phone_number, VerificationScopes.REGISTER.value)

    await ensure_phone_number_available(data.phone_number)
    if data.verification_method == VerificationMethods.CALL:
        return await send_phone_call_code(
            data.phone_number,
            RESET_PHONE_NUMBER_VERIFICATION_SCOPE,
        )
    return await send_phone_sms_code(data.phone_number, RESET_PHONE_NUMBER_VERIFICATION_SCOPE)


@router.post("/verification-code/verify")
async def verify_verification_code(
    data: PhoneVerificationCodeVerifyRequest,
) -> dict[str, bool]:
    if data.verification_scope == VerificationScopes.LOGIN:
        user_id = await authenticate_user(data.phone_number)
        return {
            "success": await verify_user_sms_call_code(
                user_id,
                data.verification_code,
                VerificationScopes.LOGIN.value,
            )
        }

    if data.verification_scope == VerificationScopes.REGISTER:
        await ensure_phone_number_available(data.phone_number)
        return {
            "success": await verify_phone_sms_call_code(
                data.phone_number,
                data.verification_code,
                VerificationScopes.REGISTER.value,
            )
        }

    await ensure_phone_number_available(data.phone_number)
    return {
        "success": await verify_phone_sms_call_code(
            data.phone_number,
            data.verification_code,
            RESET_PHONE_NUMBER_VERIFICATION_SCOPE,
        )
    }
