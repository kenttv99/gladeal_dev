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


class PhoneNumberAlreadyExistsError(BaseAPIException):
    status_code = 409
    error_code = "PHONE_NUMBER_ALREADY_EXISTS"


class AccountDeletionBlockedByActiveOrdersError(BaseAPIException):
    status_code = 409
    error_code = "ACCOUNT_DELETION_BLOCKED_BY_ACTIVE_ORDERS"


class MonthOrdersLimitExceededError(BaseAPIException):
    status_code = 409
    error_code = "MONTH_ORDERS_LIMIT_EXCEEDED"


class OrderNotFoundError(BaseAPIException):
    status_code = 404
    error_code = "ORDER_NOT_FOUND"


class OrderAlreadyAcceptedError(BaseAPIException):
    status_code = 409
    error_code = "ORDER_ALREADY_ACCEPTED"


class OrderSelfExecutionForbiddenError(BaseAPIException):
    status_code = 403
    error_code = "ORDER_SELF_EXECUTION_FORBIDDEN"


class InvalidCredentialsError(BaseAPIException):
    status_code = 401
    error_code = "INVALID_CREDENTIALS"


class InvalidAccessTokenError(BaseAPIException):
    status_code = 401
    error_code = "INVALID_ACCESS_TOKEN"


class AccessTokenExpiredError(BaseAPIException):
    status_code = 401
    error_code = "ACCESS_TOKEN_EXPIRED"


class InvalidRefreshTokenError(BaseAPIException):
    status_code = 401
    error_code = "INVALID_REFRESH_TOKEN"


class RefreshTokenExpiredError(BaseAPIException):
    status_code = 401
    error_code = "REFRESH_TOKEN_EXPIRED"


class AccessDeniedError(BaseAPIException):
    status_code = 403
    error_code = "ACCESS_DENIED"


class ValidationError(BaseAPIException):
    status_code = 422
    error_code = "VALIDATION_ERROR"
