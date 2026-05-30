from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.enums.enums_v1 import OrderStates

from .base import Base, enum_column

if TYPE_CHECKING:
    from .users import User


class Order(Base):
    """Сделка:
    title - название сделки
    conditions - произвольные условия сделки (1 блок условий), которые вводит заказчик
    result_requirements - условия из поля "Подробно Опишите в каком виде исполнитель должен предоставить результат"
    violation_proof_requirements - условия из поля "Подробно опишите, как вы можете подтвердить нарушение условий"
    slug - уникальный идентификатор сделки
    price - цена сделки
    status - статус сделки
    created_at - дата создания сделки
    updated_at - дата обновления сделки
    completed_at - дата завершения сделки
    """

    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_client_id", "client_id"),
        Index("ix_orders_performer_id", "performer_id"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    performer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    conditions: Mapped[str] = mapped_column(Text, nullable=False)
    result_requirements: Mapped[str] = mapped_column(Text, nullable=False)
    violation_proof_requirements: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[OrderStates] = mapped_column(
        enum_column(OrderStates, "order_states"),
        nullable=False,
        default=OrderStates.AWAITING_PERFORMER,
        server_default=OrderStates.AWAITING_PERFORMER.value,
    )
    checked_by_worker_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    expire_in: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)

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
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    client: Mapped["User"] = relationship(
        "User",
        back_populates="client_orders",
        foreign_keys=[client_id],
    )
    performer: Mapped["User | None"] = relationship(
        "User",
        back_populates="performer_orders",
        foreign_keys=[performer_id],
    )
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        "OrderStatusHistory",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderStatusHistory(Base):
    """История статусов сделки"""

    __tablename__ = "order_status_history"
    __table_args__ = (
        Index("ix_order_status_history_order_id", "order_id"),
        Index("ix_order_status_history_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    old_status: Mapped[OrderStates | None] = mapped_column(
        enum_column(OrderStates, "order_history_old_states"),
        nullable=True,
    )
    new_status: Mapped[OrderStates] = mapped_column(
        enum_column(OrderStates, "order_history_new_states"),
        nullable=False,
    )
    changed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    order: Mapped["Order"] = relationship("Order", back_populates="status_history")
    changed_by_user: Mapped["User | None"] = relationship("User")
