from api.exceptions.exceptions import (
    BaseAPIException,
    UserNotFoundError,
    PhoneNumberAlreadyExistsError,
    AccountDeletionBlockedByActiveOrdersError,
    MonthOrdersLimitExceededError,
    InvalidCredentialsError,
    AccessDeniedError,
    ValidationError,
)
from api.exceptions.handler import register_exception_handlers

__all__ = [
    "BaseAPIException",
    "UserNotFoundError",
    "PhoneNumberAlreadyExistsError",
    "AccountDeletionBlockedByActiveOrdersError",
    "MonthOrdersLimitExceededError",
    "InvalidCredentialsError",
    "AccessDeniedError",
    "ValidationError",
    "register_exception_handlers",
]
