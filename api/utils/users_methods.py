from sqlalchemy import delete, exists, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from api.enums.enums_v1 import OrderStates
from api.exceptions import (
    AccountDeletionBlockedByActiveOrdersError,
    PhoneNumberAlreadyExistsError,
    UserBannedError,
    UserNotFoundError,
)
from database.config import AsyncSessionLocal
from database.models.notifications import Notification
from database.models.orders import Order, OrderStatusHistory
from database.models.users import User


ACCOUNT_DELETION_BLOCKING_STATUSES = (
    OrderStates.AWAITING_PERFORMER.value,
    OrderStates.AWAITING_PAYMENT.value,
    OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
    OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
    OrderStates.AWAITING_CONFLICT.value,
    OrderStates.OPEN_CONFLICT.value,
)


async def register_user(
    first_name: str,
    last_name: str,
    phone_number: str,
    ppd: bool = False,
) -> User:
    
    """
    
    
    """
    async with AsyncSessionLocal() as session:
        try:
            async with session.begin():
                result = await session.execute(
                    insert(User)
                    .values(
                        first_name=first_name,
                        last_name=last_name,
                        phone_number=phone_number,
                        ppd=ppd,
                    )
                    .returning(User)
                )
                return result.scalar_one()
        except IntegrityError as exc:
            if "uq_users_phone_number" in str(exc.orig):
                raise PhoneNumberAlreadyExistsError() from exc
            raise


async def delete_account(user_id: int) -> None:
    user_orders = select(Order.id).where(
        or_(Order.client_id == user_id, Order.performer_id == user_id)
    )

    async with AsyncSessionLocal() as session:
        async with session.begin():
            has_active_orders = await session.scalar(
                select(
                    exists().where(
                        or_(Order.client_id == user_id, Order.performer_id == user_id),
                        Order.status.in_(ACCOUNT_DELETION_BLOCKING_STATUSES),
                    )
                )
            )
            if has_active_orders:
                raise AccountDeletionBlockedByActiveOrdersError()

            await session.execute(
                delete(OrderStatusHistory)
                .where(OrderStatusHistory.order_id.in_(user_orders))
                .execution_options(synchronize_session=False)
            )
            await session.execute(
                delete(Order).where(Order.id.in_(user_orders)).execution_options(
                    synchronize_session=False
                )
            )
            await session.execute(delete(Notification).where(Notification.user_id == user_id))
            await session.execute(
                update(OrderStatusHistory)
                .where(OrderStatusHistory.changed_by_user_id == user_id)
                .values(changed_by_user_id=None)
                .execution_options(synchronize_session=False)
            )

            result = await session.execute(delete(User).where(User.id == user_id).returning(User.id))
            if result.scalar_one_or_none() is None:
                raise UserNotFoundError()


async def authenticate_user(phone_number: str) -> int:
    async with AsyncSessionLocal() as session:
        user_id = await session.scalar(select(User.id).where(User.phone_number == phone_number))
        if user_id is None:
            raise UserNotFoundError()
        return user_id


async def get_user_phone_number(user_id: int) -> str:
    async with AsyncSessionLocal() as session:
        phone_number = await session.scalar(select(User.phone_number).where(User.id == user_id))
        if phone_number is None:
            raise UserNotFoundError()
        return phone_number


async def ensure_user_not_banned(user_id: int) -> None:
    async with AsyncSessionLocal() as session:
        is_banned = await session.scalar(select(User.is_banned).where(User.id == user_id))
        if is_banned is None:
            raise UserNotFoundError()
        if is_banned:
            raise UserBannedError()


async def reset_phone_number(user_id: int, phone_number: str) -> None:
    async with AsyncSessionLocal() as session:
        try:
            async with session.begin():
                phone_number_owner_id = await session.scalar(
                    select(User.id).where(User.phone_number == phone_number, User.id != user_id)
                )
                if phone_number_owner_id is not None:
                    raise PhoneNumberAlreadyExistsError()

                result = await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(phone_number=phone_number)
                    .returning(User.id)
                )
                if result.scalar_one_or_none() is None:
                    raise UserNotFoundError()
        except IntegrityError as exc:
            if "uq_users_phone_number" in str(exc.orig):
                raise PhoneNumberAlreadyExistsError() from exc
            raise
