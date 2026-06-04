from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from api.enums.enums_v1 import OrderStates


class RegisterUserRequest(BaseModel):
    first_name: str
    last_name: str
    phone_number: str
    ppd: bool = False


class DeleteAccountRequest(BaseModel):
    user_id: int


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
    user_id: int
    phone_number: str


class CreateOrderRequest(BaseModel):
    user_id: int
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


class ApproveOrderRequest(BaseModel):
    order_id: int
    user_id: int


class PaymentOrderRequest(BaseModel):
    order_id: int
    user_id: int


class PerformerConfirmOrderRequest(BaseModel):
    order_id: int
    user_id: int


class ClientConfirmOrderRequest(BaseModel):
    order_id: int
    user_id: int


class PerformerDeclineOrderRequest(BaseModel):
    order_id: int
    user_id: int


class ClientSoftDeclineOrderRequest(BaseModel):
    order_id: int
    user_id: int


class ClientHardDeclineOrderRequest(BaseModel):
    order_id: int
    user_id: int


class PerformerConflictOrderRequest(BaseModel):
    order_id: int
    user_id: int


###
# Платежные схемы
###

class PaymentParticipant(BaseModel):
    client_ref: str
    email: str
    phone: str | None = None


class RegisterDealPaymentRequest(BaseModel):
    order_id: int
    customer: PaymentParticipant
    performer: PaymentParticipant
    amount: int
    service_fee_amount: Decimal
    customer_payment_amount: Decimal
    performer_payout_amount: Decimal
    expires_at: datetime
    reference: str
    description: str
    currency: int = 643
    fee: int | None = None
    url: str | None = None
    failurl: str | None = None
    life_period: int | None = None
    sd_ref: str | None = None
    notify_url: str | None = None
    mode: int = 0


class RegisterDealPaymentResponse(BaseModel):
    paygine_order_id: str
    signature: str
    customer_ref: str
    performer_ref: str
    response_data: dict[str, str]
    raw_response: str
