from datetime import datetime, timezone


def ensure_utc(value: datetime) -> datetime:
    """Приводим datetime к timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
