from pydantic import BaseModel


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
