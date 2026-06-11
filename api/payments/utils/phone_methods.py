from api.exceptions import ValidationError


PAYGINE_PHONE_MIN_DIGITS = 10
PAYGINE_PHONE_MAX_DIGITS = 15


def normalize_paygine_phone(phone: str | None) -> str | None:
    if phone is None:
        return None

    digits = "".join(char for char in phone if char.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        digits = f"7{digits[1:]}"
    if not PAYGINE_PHONE_MIN_DIGITS <= len(digits) <= PAYGINE_PHONE_MAX_DIGITS:
        raise ValidationError(
            details={
                "field": "phone_number",
                "value": phone,
                "reason": "Phone number must contain 10 to 15 digits.",
            }
        )
    return digits
