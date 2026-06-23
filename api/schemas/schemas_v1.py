from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from api.enums.enums_v1 import OrderStates, UserRoles


###
# Пользователи и авторизация
###

class RegisterUserRequest(BaseModel):
    first_name: str
    last_name: str
    phone_number: str
    ppd: bool = False


class AuthUserResponse(BaseModel):
    access_token: str
    refresh_token: str
    refresh_token_expires_at: datetime
    token_type: str = "bearer"


class AuthAdminResponse(BaseModel):
    access_token: str
    refresh_token: str
    refresh_token_expires_at: datetime
    token_type: str = "bearer"


class AccessTokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: int
    first_name: str
    last_name: str
    phone_number: str
    ppd: bool
    is_banned: bool
    ban_reason: str | None
    banned_at: datetime | None
    role: UserRoles
    created_at: datetime
    updated_at: datetime
    successful_orders_count: int
    unsuccessful_orders_count: int
    conflict_orders_count: int


class AdminUsersResponse(BaseModel):
    limit: int
    has_more: bool
    next_cursor_created_at: datetime | None
    next_cursor_id: int | None
    items: list[AdminUserResponse]


class AdminUserBanResponse(BaseModel):
    id: int
    is_banned: bool
    ban_reason: str | None
    banned_at: datetime | None


class AdminOrderResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    order_id: int
    client_id: int
    performer_id: int | None
    status: OrderStates
    created_at: datetime
    completed_at: datetime | None


class AdminOrdersResponse(BaseModel):
    limit: int
    has_more: bool
    next_cursor_created_at: datetime | None
    next_cursor_id: int | None
    items: list[AdminOrderResponse]


class AdminOrderStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: int
    order_id: int
    old_status: OrderStates | None
    new_status: OrderStates
    changed_by_user_id: int | None
    created_at: datetime


class AdminOrderInfoResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: int
    client_id: int
    performer_id: int | None
    title: str
    conditions: str
    result_requirements: str
    violation_proof_requirements: str
    slug: str
    price: Decimal
    status: OrderStates
    checked_by_worker_at: datetime | None
    expire_in: datetime
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    status_history: list[AdminOrderStatusHistoryResponse]


###
# Сделки
###

class CreateOrderRequest(BaseModel):
    customer_email: str
    title: str
    conditions: str
    result_requirements: str
    violation_proof_requirements: str
    price: Decimal
    expire_in: datetime


class OrderInfoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    client_id: int
    performer_id: int | None
    title: str
    conditions: str
    result_requirements: str
    violation_proof_requirements: str
    slug: str
    price: Decimal
    status: OrderStates
    created_at: datetime
    updated_at: datetime
    expire_in: datetime
    completed_at: datetime | None


class OrderInfoWithPaymentDataResponse(OrderInfoResponse):
    customer_email: str | None = None
    performer_email: str | None = None


class CreateOrderResponse(OrderInfoWithPaymentDataResponse):
    service_fee_amount: Decimal


###
# Платежи: регистрация сделок
###

class RegisterDealCustomer(BaseModel):
    client_ref: str
    email: str
    phone: str | None = None


class RegisterDealPerformer(BaseModel):
    client_ref: str
    email: str
    phone: str | None = None


class RegisterDealPaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: int
    customer: RegisterDealCustomer
    amount: Decimal
    reference: str
    description: str
    notify_url: str
    currency: int = 643


class RegisterPayoutDealProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: int
    performer: RegisterDealPerformer
    amount: Decimal
    reference: str
    description: str
    notify_url: str
    currency: int = 643


class RegisterPayoutDealPaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: int
    performer_id: int
    performer_email: str
    performer_phone: str | None = None
    amount: Decimal
    description: str
    currency: int = 643


class RegisterDepositDealPaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: int
    client_id: int
    customer_email: str
    customer_phone: str
    amount: Decimal
    description: str
    currency: int = 643


class RefundMoneyPaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: int
    client_id: int
    customer_email: str
    customer_phone: str | None = None
    amount: Decimal
    description: str
    currency: int = 643


class DepositDealPaymentValues(BaseModel):
    currency: int
    order_amount: Decimal
    service_fee_amount: Decimal
    paygine_payment_operation_id: str
    expire_payment_at: datetime


class RegisterDepositDealPaymentResponse(BaseModel):
    provider_response: dict[str, object]
    payment_values: DepositDealPaymentValues


class PayoutDealPaymentValues(BaseModel):
    paygine_payout_operation_id: str
    expire_payout_at: datetime


class RegisterPayoutDealPaymentResponse(BaseModel):
    provider_response: dict[str, object]
    payment_values: PayoutDealPaymentValues
