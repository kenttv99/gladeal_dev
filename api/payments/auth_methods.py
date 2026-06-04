from base64 import b64encode
from collections.abc import Iterable
from hashlib import sha256
from hmac import compare_digest

from api.payments.config import PAYGINE_SIGNATURE_PASSWORD


def build_signature(
    values: Iterable[object],
    password: str = PAYGINE_SIGNATURE_PASSWORD,
) -> str:
    """Формирует цифровую подпись Paygine из значений параметров."""
    raw_signature = "".join(str(value) for value in values) + password
    hex_digest = sha256(raw_signature.encode("utf-8")).hexdigest()
    return b64encode(hex_digest.encode("utf-8")).decode("ascii")


def is_valid_signature(
    values: Iterable[object],
    signature: str,
    password: str = PAYGINE_SIGNATURE_PASSWORD,
) -> bool:
    """Проверяет цифровую подпись Paygine."""
    return compare_digest(build_signature(values, password), signature)
