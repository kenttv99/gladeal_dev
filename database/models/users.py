from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Numeric, String, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.enums.enums_v1 import UserRoles, AdminRoles

from .base import Base, enum_column

if TYPE_CHECKING:
    from .notifications import Notification
    from .orders import Order


class User(Base):
    """Пользователь системы: клиент или исполнитель."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    patronymic: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    birth_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    persondoc_number: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    month_sum_limit: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("200000.00"),
        server_default="200000.00",
    )
    ppd: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    is_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    ban_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    role: Mapped[UserRoles] = mapped_column(
        enum_column(UserRoles, "user_roles"),
        nullable=False,
        default=UserRoles.CLIENT,
        server_default=UserRoles.CLIENT.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    kyc_data: Mapped["KYCData | None"] = relationship(
        "KYCData",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    client_orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="client",
        foreign_keys="Order.client_id",
    )
    performer_orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="performer",
        foreign_keys="Order.performer_id",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="user",
    )
    refresh_tokens: Mapped[list["UserRefreshToken"]] = relationship(
        "UserRefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class KYCData(Base):
    """KYC данные пользователя"""

    __tablename__ = "kyc_data"
    __table_args__ = (
        Index("ix_kyc_data_user_id", "user_id", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    kyc_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    kyc_status: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="kyc_data")



class UserRefreshToken(Base):
    """Refresh токен с привязкой к id пользователя"""

    __tablename__ = "user_refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


class Admin(Base):
    """Пользователь системы: администраторы и саппорты"""

    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[AdminRoles] = mapped_column(
        enum_column(AdminRoles, "admin_roles"),
        nullable=False,
        default=AdminRoles.ADMIN,
        server_default=AdminRoles.ADMIN.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    refresh_tokens: Mapped[list["AdminRefreshToken"]] = relationship(
        "AdminRefreshToken",
        back_populates="admin",
        cascade="all, delete-orphan",
    )


class AdminRefreshToken(Base):
    """Refresh токен с привязкой к id админа"""

    __tablename__ = "admin_refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    admin_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    admin: Mapped["Admin"] = relationship("Admin", back_populates="refresh_tokens")
