from datetime import datetime

from sqlalchemy import BigInteger, Boolean, String, DateTime

from api.enums.enums_v1 import UserRoles

from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, enum_column


class Client(Base):
    """Клиентская база"""
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    ppd: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    role: Mapped[str] = mapped_column(enum_column(UserRoles, "user_roles"), nullable=False, default=UserRoles.CLIENT.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
