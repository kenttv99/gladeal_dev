from datetime import datetime
from decimal import Decimal

from sqlalchemy import exists, func, insert, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from api.enums.enums_v1 import OrderStates, UserRoles
from api.exceptions import (
    MonthOrdersLimitExceededError,
    OrderAlreadyAcceptedError,
    OrderNotFoundError,
    OrderSelfExecutionForbiddenError,
    UserNotFoundError,
    ValidationError,
)
from api.payments.payments_methods import register_deposit_deal
from api.schemas.schemas_v1 import RegisterDepositDealPaymentRequest
from api.utils.help_orders_method import check_user_month_orders_limit
from api.utils.help_orders_method import generate_order_link, generate_order_slug
from database.config import AsyncSessionLocal
from database.models.orders import Order, OrderStatusHistory
from database.models.payments import OrderPaymentData
from database.models.users import User


ACTIVE_ORDER_STATUSES = (
    OrderStates.AWAITING_PERFORMER.value,
    OrderStates.AWAITING_PAYMENT.value,
    OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
    OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
    OrderStates.AWAITING_CONFLICT.value,
    OrderStates.OPEN_CONFLICT.value,
    OrderStates.AWAITING_PERFORMER_PAYOUT.value
)

CLOSED_ORDER_STATUSES = (
    OrderStates.SUCCESSFUL_COMPLETION.value,
    OrderStates.UNSUCCESSFUL_COMPLETION.value,
    OrderStates.CANCLED_BY_EXPIRE_TIME.value,
    OrderStates.CONFIRM_BY_EXPIRE_TIME_TO_PERFORMER.value,
    OrderStates.CLOSED_BY_ARBITER_TO_CLIENT.value,
    OrderStates.CLOSED_BY_ARBITER_TO_PERFORMER.value,
)


def _order_status_values(status: str) -> dict[str, object]:
    values: dict[str, object] = {"status": status}
    if status == OrderStates.AWAITING_CLIENT_CONFIRMATION.value or status in CLOSED_ORDER_STATUSES:
        values["completed_at"] = func.now()
    return values


async def create_order(
    client_id: int,
    customer_email: str,
    title: str,
    conditions: str,
    result_requirements: str,
    violation_proof_requirements: str,
    price: Decimal,
    expire_in: datetime,
) -> Order:
    
    """
    Метод создает ордер и проверяет месячный лимит для пользователя, установленный в .env, производит запрос к платежной системе, получает ответ и записывает данные в таблицы.
    Состояние дублируется в таблицу историй состояний сделки.
    
    """

    order, customer_phone = await _create_order_record(
        client_id=client_id,
        title=title,
        conditions=conditions,
        result_requirements=result_requirements,
        violation_proof_requirements=violation_proof_requirements,
        price=price,
        expire_in=expire_in,
    )
    payment_result = await register_deposit_deal(
        RegisterDepositDealPaymentRequest(
            order_id=order.id,
            client_id=order.client_id,
            customer_email=customer_email,
            customer_phone=customer_phone,
            amount=order.price,
            expires_at=order.expire_in,
            description=order.title,
        )
    )
    await _create_order_payment_data(
        order.id,
        customer_email,
        payment_result.payment_values.model_dump(),
    )
    return order


async def _create_order_record(
    client_id: int,
    title: str,
    conditions: str,
    result_requirements: str,
    violation_proof_requirements: str,
    price: Decimal,
    expire_in: datetime,
) -> tuple[Order, str]:
    while True:
        async with AsyncSessionLocal() as session:
            try:
                async with session.begin():
                    customer_phone = await session.scalar(
                        select(User.phone_number).where(User.id == client_id)
                    )
                    if customer_phone is None:
                        raise UserNotFoundError()

                    limit_check = await check_user_month_orders_limit(session, client_id, price)
                    if limit_check["is_limit_exceeded"]:
                        raise MonthOrdersLimitExceededError(details=limit_check)

                    result = await session.execute(
                        insert(Order)
                        .values(
                            client_id=client_id,
                            title=title,
                            conditions=conditions,
                            result_requirements=result_requirements,
                            violation_proof_requirements=violation_proof_requirements,
                            slug=await generate_order_slug(session),
                            price=price,
                            expire_in=expire_in,
                            status=OrderStates.AWAITING_PERFORMER.value,
                        )
                        .returning(Order)
                    )
                    order = result.scalar_one()

                    await session.execute(
                        insert(OrderStatusHistory).values(
                            order_id=order.id,
                            old_status=None,
                            new_status=OrderStates.AWAITING_PERFORMER.value,
                            changed_by_user_id=client_id,
                        )
                    )
                    return order, customer_phone
            except IntegrityError as exc:
                if "uq_orders_slug" in str(exc.orig):
                    continue
                raise


async def _create_order_payment_data(
    order_id: int,
    customer_email: str,
    payment_values: dict[str, object],
) -> None:
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(
                    insert(OrderPaymentData).values(
                        order_id=order_id,
                        customer_email=customer_email,
                        **payment_values,
                    )
                )
    except SQLAlchemyError as exc:
        exc.payment_data = {
            "order_id": order_id,
            **{
                key: value.isoformat()
                if isinstance(value, datetime)
                else str(value)
                if isinstance(value, Decimal)
                else value
                for key, value in payment_values.items()
            },
        }
        raise


async def get_order_link(order_id: int, client_id: int) -> str:

    """
    Метод получает slug ордера и генерирует полноценную ссылку для перехода на страницу с информацией о сделке
    
    """

    async with AsyncSessionLocal() as session:
        slug = await session.scalar(
            select(Order.slug).where(Order.id == order_id, Order.client_id == client_id)
        )
        if slug is None:
            raise OrderNotFoundError()
        return generate_order_link(slug)


async def get_order_by_slug(slug: str, authorized_user_id: int) -> Order:
    """Достаем информацию об ордере по слагу"""
    async with AsyncSessionLocal() as session:
        order = await session.scalar(
            select(Order).where(Order.slug == slug)
        )
        if order is None:
            raise OrderNotFoundError()
        return order


async def get_active_orders_by_role(role: UserRoles | str, user_id: int) -> list[Order]:
    """Получаем список активных ордеров в зависимости от роли пользователя"""
    role_value = role.value if isinstance(role, UserRoles) else role
    if role_value not in {UserRoles.CLIENT.value, UserRoles.PERFORMER.value}:
        raise ValidationError()

    async with AsyncSessionLocal() as session:
        query = select(Order).where(Order.status.in_(ACTIVE_ORDER_STATUSES))
        if role_value == UserRoles.CLIENT.value:
            query = query.where(Order.client_id == user_id)
        if role_value == UserRoles.PERFORMER.value:
            query = query.where(Order.performer_id == user_id)

        result = await session.scalars(
            query.order_by(Order.created_at.desc())
        )
        return list(result.all())


async def approve_order(order_id: int, performer_id: int) -> None:
    """Переводим сделку в состояние ожидания оплаты"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            performer_exists = await session.scalar(
                select(exists().where(User.id == performer_id))
            )
            if not performer_exists:
                raise UserNotFoundError()

            order_data = await session.execute(
                select(Order.status, Order.performer_id, Order.client_id)
                .where(Order.id == order_id)
                .with_for_update()
            )
            order_row = order_data.one_or_none()
            if order_row is None:
                raise OrderNotFoundError()
            current_status, current_performer_id, client_id = order_row
            if client_id == performer_id:
                raise OrderSelfExecutionForbiddenError()
            current_status_value = (
                current_status.value
                if isinstance(current_status, OrderStates)
                else current_status
            )
            if (
                current_performer_id is not None
                or current_status_value != OrderStates.AWAITING_PERFORMER.value
            ):
                raise OrderAlreadyAcceptedError()

            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(
                    performer_id=performer_id,
                    **_order_status_values(OrderStates.AWAITING_PAYMENT.value),
                )
            )
            await session.execute(
                insert(OrderStatusHistory).values(
                    order_id=order_id,
                    old_status=current_status_value,
                    new_status=OrderStates.AWAITING_PAYMENT.value,
                    changed_by_user_id=performer_id,
                )
            )


async def payment_order(order_id: int, client_id: int) -> None:
    """Переводим сделку в состояние после оплаты и ожидания выполнения сделки со стороны исполнителя"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            client_exists = await session.scalar(
                select(exists().where(User.id == client_id))
            )
            if not client_exists:
                raise UserNotFoundError()

            current_status = await session.scalar(
                select(Order.status)
                .where(Order.id == order_id, Order.client_id == client_id)
                .with_for_update()
            )
            if current_status is None:
                raise OrderNotFoundError()

            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(**_order_status_values(OrderStates.AWAITING_PERFORMER_CONFIRMATION.value))
            )
            await session.execute(
                insert(OrderStatusHistory).values(
                    order_id=order_id,
                    old_status=(
                        current_status.value
                        if isinstance(current_status, OrderStates)
                        else current_status
                    ),
                    new_status=OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
                    changed_by_user_id=client_id,
                )
            )


async def performer_confirm_order(order_id: int, performer_id: int) -> None:
    """Переводим сделку в состояние ожидания подтверждения заказчиком"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            performer_exists = await session.scalar(
                select(exists().where(User.id == performer_id))
            )
            if not performer_exists:
                raise UserNotFoundError()

            order_data = await session.execute(
                select(Order.status, Order.client_id)
                .where(Order.id == order_id, Order.performer_id == performer_id)
                .with_for_update()
            )
            order_row = order_data.one_or_none()
            if order_row is None:
                raise OrderNotFoundError()
            current_status, client_id = order_row
            if client_id == performer_id:
                raise OrderSelfExecutionForbiddenError()

            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(**_order_status_values(OrderStates.AWAITING_CLIENT_CONFIRMATION.value))
            )
            await session.execute(
                insert(OrderStatusHistory).values(
                    order_id=order_id,
                    old_status=(
                        current_status.value
                        if isinstance(current_status, OrderStates)
                        else current_status
                    ),
                    new_status=OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
                    changed_by_user_id=performer_id,
                )
            )


async def client_confirm_order(order_id: int, client_id: int) -> None:
    """Переводим сделку в состояние успешного завершения и ожидания получения выплаты исполнителем"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            client_exists = await session.scalar(
                select(exists().where(User.id == client_id))
            )
            if not client_exists:
                raise UserNotFoundError()

            current_status = await session.scalar(
                select(Order.status)
                .where(Order.id == order_id, Order.client_id == client_id)
                .with_for_update()
            )
            if current_status is None:
                raise OrderNotFoundError()

            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(**_order_status_values(OrderStates.AWAITING_PERFORMER_PAYOUT.value))
            )
            await session.execute(
                insert(OrderStatusHistory).values(
                    order_id=order_id,
                    old_status=(
                        current_status.value
                        if isinstance(current_status, OrderStates)
                        else current_status
                    ),
                    new_status=OrderStates.AWAITING_PERFORMER_PAYOUT.value,
                    changed_by_user_id=client_id,
                )
            )


async def performer_order_payout(order_id: int, performer_id: int) -> None:
    """Переводим сделку в состояние успешного завершения после выплаты исполнителю"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            performer_exists = await session.scalar(
                select(exists().where(User.id == performer_id))
            )
            if not performer_exists:
                raise UserNotFoundError()

            order_data = await session.execute(
                select(Order.status, Order.client_id)
                .where(Order.id == order_id, Order.performer_id == performer_id)
                .with_for_update()
            )
            order_row = order_data.one_or_none()
            if order_row is None:
                raise OrderNotFoundError()
            current_status, client_id = order_row
            if client_id == performer_id:
                raise OrderSelfExecutionForbiddenError()
            current_status_value = (
                current_status.value
                if isinstance(current_status, OrderStates)
                else current_status
            )
            if current_status_value != OrderStates.AWAITING_PERFORMER_PAYOUT.value:
                raise ValidationError()

            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(**_order_status_values(OrderStates.SUCCESSFUL_COMPLETION.value))
            )
            await session.execute(
                insert(OrderStatusHistory).values(
                    order_id=order_id,
                    old_status=current_status_value,
                    new_status=OrderStates.SUCCESSFUL_COMPLETION.value,
                    changed_by_user_id=performer_id,
                )
            )


async def performer_decline_order(order_id: int, performer_id: int) -> None:
    """Переводим сделку в состояние неуспешного завершения по отказу исполнителя"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            performer_exists = await session.scalar(
                select(exists().where(User.id == performer_id))
            )
            if not performer_exists:
                raise UserNotFoundError()

            order_data = await session.execute(
                select(Order.status, Order.client_id)
                .where(Order.id == order_id, Order.performer_id == performer_id)
                .with_for_update()
            )
            order_row = order_data.one_or_none()
            if order_row is None:
                raise OrderNotFoundError()
            current_status, client_id = order_row
            if client_id == performer_id:
                raise OrderSelfExecutionForbiddenError()

            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(**_order_status_values(OrderStates.UNSUCCESSFUL_COMPLETION.value))
            )
            await session.execute(
                insert(OrderStatusHistory).values(
                    order_id=order_id,
                    old_status=(
                        current_status.value
                        if isinstance(current_status, OrderStates)
                        else current_status
                    ),
                    new_status=OrderStates.UNSUCCESSFUL_COMPLETION.value,
                    changed_by_user_id=performer_id,
                )
            )


async def client_softdecline_order(order_id: int, client_id: int) -> None:
    """Переводим сделку в неуспешное завершение, если исполнитель еще не принял ее"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            client_exists = await session.scalar(
                select(exists().where(User.id == client_id))
            )
            if not client_exists:
                raise UserNotFoundError()

            order_data = await session.execute(
                select(Order.status, Order.performer_id)
                .where(Order.id == order_id, Order.client_id == client_id)
                .with_for_update()
            )
            order_row = order_data.one_or_none()
            if order_row is None:
                raise OrderNotFoundError()
            current_status, performer_id = order_row
            if performer_id is not None:
                raise OrderAlreadyAcceptedError()

            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(**_order_status_values(OrderStates.UNSUCCESSFUL_COMPLETION.value))
            )
            await session.execute(
                insert(OrderStatusHistory).values(
                    order_id=order_id,
                    old_status=(
                        current_status.value
                        if isinstance(current_status, OrderStates)
                        else current_status
                    ),
                    new_status=OrderStates.UNSUCCESSFUL_COMPLETION.value,
                    changed_by_user_id=client_id,
                )
            )


async def client_harddecline_order(order_id: int, client_id: int) -> None:
    """Переводим сделку в состояние ожидания подтверждения отказа исполнителем"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            client_exists = await session.scalar(
                select(exists().where(User.id == client_id))
            )
            if not client_exists:
                raise UserNotFoundError()

            current_status = await session.scalar(
                select(Order.status)
                .where(Order.id == order_id, Order.client_id == client_id)
                .with_for_update()
            )
            if current_status is None:
                raise OrderNotFoundError()

            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(**_order_status_values(OrderStates.AWAITING_CONFLICT.value))
            )
            await session.execute(
                insert(OrderStatusHistory).values(
                    order_id=order_id,
                    old_status=(
                        current_status.value
                        if isinstance(current_status, OrderStates)
                        else current_status
                    ),
                    new_status=OrderStates.AWAITING_CONFLICT.value,
                    changed_by_user_id=client_id,
                )
            )


async def performer_conflict_order(order_id: int, performer_id: int) -> None:
    """Переводим сделку в состояние открытого спора исполнителем"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            performer_exists = await session.scalar(
                select(exists().where(User.id == performer_id))
            )
            if not performer_exists:
                raise UserNotFoundError()

            order_data = await session.execute(
                select(Order.status, Order.client_id)
                .where(Order.id == order_id, Order.performer_id == performer_id)
                .with_for_update()
            )
            order_row = order_data.one_or_none()
            if order_row is None:
                raise OrderNotFoundError()
            current_status, client_id = order_row
            if client_id == performer_id:
                raise OrderSelfExecutionForbiddenError()

            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(**_order_status_values(OrderStates.OPEN_CONFLICT.value))
            )
            await session.execute(
                insert(OrderStatusHistory).values(
                    order_id=order_id,
                    old_status=(
                        current_status.value
                        if isinstance(current_status, OrderStates)
                        else current_status
                    ),
                    new_status=OrderStates.OPEN_CONFLICT.value,
                    changed_by_user_id=performer_id,
                )
            )


async def get_client_closed_orders(client_id: int) -> list[Order]:
    """Получаем список закрытых сделок заказчика"""
    async with AsyncSessionLocal() as session:
        result = await session.scalars(
            select(Order)
            .where(Order.status.in_(CLOSED_ORDER_STATUSES), Order.client_id == client_id)
            .order_by(Order.updated_at.desc())
        )
        return list(result.all())


async def get_performer_closed_orders(performer_id: int) -> list[Order]:
    """Получаем список закрытых сделок исполнителя"""
    async with AsyncSessionLocal() as session:
        result = await session.scalars(
            select(Order)
            .where(
                Order.status.in_(CLOSED_ORDER_STATUSES),
                Order.performer_id == performer_id,
            )
            .order_by(Order.updated_at.desc())
        )
        return list(result.all())
