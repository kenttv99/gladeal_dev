from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from api.enums.enums_v1 import OrderStates


###
# Пользователи и авторизация
###

class RegisterUserRequest(BaseModel):
    first_name: str
    last_name: str
    phone_number: str
    ppd: bool = False


class AuthUserRequest(BaseModel):
    phone_number: str


class AuthUserResponse(BaseModel):
    access_token: str
    refresh_token: str
    refresh_token_expires_at: datetime
    token_type: str = "bearer"


class AccessTokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ResetPhoneNumberRequest(BaseModel):
    phone_number: str


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


class OrderInfoRequest(BaseModel):
    slug: str


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


class CreateOrderResponse(OrderInfoResponse):
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
    expires_at: datetime
    reference: str
    description: str
    notify_url: str
    currency: int = 643


class RegisterPayoutDealPaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: int
    performer: RegisterDealPerformer
    amount: Decimal
    expires_at: datetime
    reference: str
    description: str
    notify_url: str
    currency: int = 643


class RegisterDepositDealPaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: int
    client_id: int
    customer_email: str
    customer_phone: str
    amount: Decimal
    expires_at: datetime
    description: str
    currency: int = 643


class DepositDealPaymentValues(BaseModel):
    currency: int
    order_amount: Decimal
    service_fee_amount: Decimal
    paygine_payment_operation_id: str
    expires_at: datetime


class RegisterDepositDealPaymentResponse(BaseModel):
    provider_response: dict[str, object]
    payment_values: DepositDealPaymentValues


###
# Платежи: операции по зарегистрированным сделкам
###

class CancleUnpaymentDealRequest(BaseModel):
    paygine_payment_operation_id: int


class GeneratePaymentLinkRequest(BaseModel):
    paygine_payment_operation_id: int


class GenerateWithdrowLinkRequest(BaseModel):
    paygine_payout_operation_id: int


class CompletePaymentedDealRequest(BaseModel):
    paygine_payment_operation_id: int


class RefundMoneyRequest(BaseModel):
    paygine_payment_operation_id: int
