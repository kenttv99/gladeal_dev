from __future__ import annotations


def normalize_phone_to_int(phone: int | str) -> int:
    """Нормализуем телефон к формату ProstoSMS: только цифры в int."""
    phone_digits = "".join(char for char in str(phone) if char.isdigit())
    if not phone_digits:
        raise ValueError("phone must contain digits")
    return int(phone_digits)
