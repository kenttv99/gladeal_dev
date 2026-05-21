from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class NotificationType(Base):
    """Типы уведомлений: заказ, отзыв, акция, новость"""
    __tablename__ = "notification_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

class NotificationStatus(Base):
    """Статусы уведомлений: отправлено, доставлено, прочитано, ошибка"""
    __tablename__ = "notification_statuses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

class NotificationUserType(Base):
    """Типы пользователей: клиент, исполнитель"""
    __tablename__ = "notification_user_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

class Notification(Base):
    """Уведомления"""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    notification_type_id: Mapped[int] = mapped_column(ForeignKey(NotificationType.id), nullable=False)
    status: Mapped[int] = mapped_column(ForeignKey(NotificationStatus.id), nullable=False)
    user_type_id: Mapped[int] = mapped_column(ForeignKey(NotificationUserType.id), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
