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
    token_type: str = "bearer"


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
