from datetime import datetime, timezone

from sqlalchemy import delete, exists, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from api.enums.enums_v1 import OrderStates
from api.exceptions import (
    AccountDeletionBlockedByActiveOrdersError,
    PhoneNumberAlreadyExistsError,
    UserBannedError,
    UserNotFoundError,
    UserPersondocRequiredError,
)
from api.payments.payments_methods import check_identification_status
from api.schemas.schemas_v1 import UserKYCResponse
from database.config import AsyncSessionLocal
from database.models.notifications import Notification
from database.models.orders import Order, OrderStatusHistory
from database.models.users import KYCData, User


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


async def ensure_phone_number_available(phone_number: str, user_id: int | None = None) -> None:
    async with AsyncSessionLocal() as session:
        conditions = [User.phone_number == phone_number]
        if user_id is not None:
            conditions.append(User.id != user_id)
        phone_number_owner_id = await session.scalar(select(User.id).where(*conditions))
        if phone_number_owner_id is not None:
            raise PhoneNumberAlreadyExistsError()


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


async def verify_user_kyc(user_id: int) -> UserKYCResponse:
    """Выполняет идентификацию пользователя через Paygine и сохраняет результат в KYCData."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            user = await session.scalar(select(User).where(User.id == user_id))
            if user is None:
                raise UserNotFoundError()
            if not user.persondoc_number or not user.birth_date:
                raise UserPersondocRequiredError()

            birth_date_str = user.birth_date.strftime("%Y.%m.%d")

            kyc_result = await check_identification_status(
                first_name=user.first_name,
                patronymic=user.patronymic,
                last_name=user.last_name,
                birth_date=birth_date_str,
                persondoc_number=user.persondoc_number,
            )
            data = kyc_result.get("data", {}) if isinstance(kyc_result, dict) else {}
            status = data.get("status")
            identification_level = data.get("identification_level")
            persondoc_result = data.get("persondoc_result")
            persondoc_fail_reason = data.get("persondoc_fail_reason")

            is_approved = (
                status == "APPROVED"
                and str(identification_level) in ("20", "40")
            )
            kyc_level_str = str(identification_level) if identification_level is not None else None

            now = datetime.now(timezone.utc)
            kyc_entry = await session.scalar(select(KYCData).where(KYCData.user_id == user_id))
            if kyc_entry is None:
                kyc_entry = KYCData(
                    user_id=user_id,
                    kyc_level=kyc_level_str,
                    kyc_status=is_approved,
                    created_at=now,
                    updated_at=now,
                )
                session.add(kyc_entry)
            else:
                kyc_entry.kyc_level = kyc_level_str
                kyc_entry.kyc_status = is_approved
                kyc_entry.updated_at = now

            await session.flush()

            return UserKYCResponse(
                user_id=user_id,
                kyc_status=bool(kyc_entry.kyc_status),
                kyc_level=kyc_entry.kyc_level,
                provider_status=status,
                persondoc_result=str(persondoc_result) if persondoc_result is not None else None,
                identification_level=kyc_level_str,
                persondoc_fail_reason=str(persondoc_fail_reason) if persondoc_fail_reason is not None else None,
                updated_at=now,
            )


async def get_user_kyc_data(user_id: int) -> UserKYCResponse:
    """Получает текущие KYC данные пользователя из базы данных."""
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
        if user is None:
            raise UserNotFoundError()

        kyc_entry = await session.scalar(select(KYCData).where(KYCData.user_id == user_id))
        return UserKYCResponse(
            user_id=user_id,
            kyc_status=bool(kyc_entry.kyc_status) if kyc_entry else False,
            kyc_level=kyc_entry.kyc_level if kyc_entry else None,
            updated_at=kyc_entry.updated_at if kyc_entry else None,
        )

