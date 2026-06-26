from secrets import randbelow


def generate_verification_code() -> str:
    """Генерируем 4-значный проверочный код."""
    return f"{randbelow(10000):04d}"
