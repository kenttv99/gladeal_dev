from __future__ import annotations

import base64
from hashlib import sha256
import io
import secrets

import pyotp
import qrcode
from qrcode.constants import ERROR_CORRECT_M

from api.config import JWT_SECRET_KEY
from api.exceptions import TwoFactorCodeAlreadyUsedError
from api.sms_calls.redis_client import get_sms_calls_redis


def generate_two_factor_secret() -> str:
    """Генерирует 32-символьный Base32 секрет для TOTP."""
    return pyotp.random_base32(32)


def generate_totp_uri(secret: str, account_name: str, issuer: str = "Gladeal") -> str:
    """Формирует URI стандарта otpauth://totp/..."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=account_name, issuer_name=issuer)


def generate_qr_code_base64(totp_uri: str) -> str:
    """Генерирует Base64 Data URI строку PNG изображения QR-кода."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(totp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_bytes = buffer.getvalue()
    return f"data:image/png;base64,{base64.b64encode(qr_bytes).decode('utf-8')}"


def generate_backup_codes(count: int = 8) -> list[str]:
    """Генерирует список одноразовых резервных кодов в формате XXXX-XXXX."""
    return [
        f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
        for _ in range(count)
    ]


def hash_backup_code(code: str) -> str:
    """Хэширует резервный код с солью JWT_SECRET_KEY."""
    normalized = code.strip().upper()
    return sha256(f"{normalized}:{JWT_SECRET_KEY}".encode()).hexdigest()


def verify_and_burn_backup_code(raw_code: str, hashed_codes: list[str] | None) -> tuple[bool, list[str]]:
    """
    Проверяет резервный код среди сохраненных хэшей.
    При совпадении сжигает его (удаляет из списка) и возвращает (True, remaining_hashes).
    """
    if not hashed_codes:
        return False, []
    target_hash = hash_backup_code(raw_code)
    if target_hash in hashed_codes:
        remaining = [h for h in hashed_codes if h != target_hash]
        return True, remaining
    return False, hashed_codes


def verify_totp_code(secret: str, code: str) -> bool:
    """Валидирует 6-значный TOTP код с допустимым окном дрейфа времени +-30с."""
    if not secret or not code:
        return False
    clean_code = code.strip()
    if not clean_code.isdigit() or len(clean_code) != 6:
        return False
    totp = pyotp.TOTP(secret)
    return bool(totp.verify(clean_code, valid_window=1))


async def mark_totp_code_used(scope: str, entity_id: int, code: str) -> None:
    """
    Защита от Replay-атак: атомарно регистрирует использованный код в Redis на 90 секунд.
    Если код уже был использован в течение окна валидности, выбрасывает ошибку.
    """
    redis = get_sms_calls_redis()
    key = f"2fa:used:{scope}:{entity_id}:{code.strip()}"
    is_new = await redis.set(key, "1", ex=90, nx=True)
    if not is_new:
        raise TwoFactorCodeAlreadyUsedError()
