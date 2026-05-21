from typing import Dict, Any, Optional


class BaseAPIException(Exception):
    """Базовое исключение для всех ошибок API."""
    status_code: int = 500
    error_code: str = "INTERNAL_SERVER_ERROR"

    def __init__(
        self, 
        message_kwargs: Optional[Dict[str, Any]] = None, 
        details: Optional[Any] = None
    ):
        self.message_kwargs = message_kwargs or {}
        self.details = details
        super().__init__(self.error_code)


class UserNotFoundError(BaseAPIException):
    status_code = 404
    error_code = "USER_NOT_FOUND"


class InvalidCredentialsError(BaseAPIException):
    status_code = 401
    error_code = "INVALID_CREDENTIALS"


class AccessDeniedError(BaseAPIException):
    status_code = 403
    error_code = "ACCESS_DENIED"


class ValidationError(BaseAPIException):
    status_code = 422
    error_code = "VALIDATION_ERROR"
