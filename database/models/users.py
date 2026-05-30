from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.enums.enums_v1 import UserRoles

from .base import Base, enum_column

if TYPE_CHECKING:
    from .notifications import Notification
    from .orders import Order


class User(Base):
    """Пользователь системы: клиент или исполнитель."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    ppd: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
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
