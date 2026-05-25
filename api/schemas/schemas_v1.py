from pydantic import BaseModel


class RegisterUserRequest(BaseModel):
    first_name: str
    last_name: str
    phone_number: str
    ppd: bool = False
