from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.enums.enums_v1 import OrderPaymentStates

from .base import Base, enum_column

if TYPE_CHECKING:
    from .orders import Order


class OrderPaymentData(Base):
    """Платежные данные сделки без карточных реквизитов."""

    __tablename__ = "orders_payment_data"
    __table_args__ = (
        Index("ix_orders_payment_data_order_id", "order_id", unique=True),
        Index("ix_orders_payment_data_payment_status", "payment_status"),
        Index("ix_orders_payment_data_payout_status", "payout_status"),
        Index("ix_orders_payment_data_revoke_status", "revoke_status"),
        Index(
            "ix_orders_payment_data_paygine_payment_operation_id",
            "paygine_payment_operation_id",
            unique=True,
        ),
        Index(
            "ix_orders_payment_data_paygine_payout_operation_id",
            "paygine_payout_operation_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_email: Mapped[str] = mapped_column(String(100), nullable=False)
    performer_email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=643,
        server_default="643",
    )
    order_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    service_fee_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_status: Mapped[OrderPaymentStates] = mapped_column(
        enum_column(OrderPaymentStates, "order_payment_status_states"),
        nullable=False,
        default=OrderPaymentStates.REGISTERED,
        server_default=OrderPaymentStates.REGISTERED.value,
    )
    payout_status: Mapped[OrderPaymentStates | None] = mapped_column(
        enum_column(OrderPaymentStates, "order_payout_status_states"),
        nullable=True,
    )
    revoke_status: Mapped[OrderPaymentStates | None] = mapped_column(
        enum_column(OrderPaymentStates, "order_revoke_status_states"),
        nullable=True,
    )
    paygine_payment_operation_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    paygine_payout_operation_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    paygine_revoked_operation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expire_payment_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    expire_payout_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    payout_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    payment_complete_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    order: Mapped["Order"] = relationship("Order", back_populates="payment_data")
