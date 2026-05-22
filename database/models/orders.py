from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from api.enums.enums_v1 import OrderStates

from .base import Base, enum_column


class Order(Base):
    """Сделка"""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    conditions: Mapped[str] = mapped_column(String, nullable=False)
    result_requirements: Mapped[str] = mapped_column(String, nullable=False)
    violation_proof_requirements: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[OrderStates] = mapped_column(
        enum_column(OrderStates, "order_states"),
        nullable=False,
        default=OrderStates.AWAITING_PERFORMER,
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
