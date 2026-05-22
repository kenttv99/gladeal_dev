from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from api.enums.enums_v1 import OrderStates

from .base import Base, enum_column


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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    conditions: Mapped[str] = mapped_column(String, nullable=False)
    result_requirements: Mapped[str] = mapped_column(String, nullable=False)
    violation_proof_requirements: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        enum_column(OrderStates, "order_states"),
        nullable=False,
        default=OrderStates.AWAITING_PERFORMER.value,
    )
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=True)
