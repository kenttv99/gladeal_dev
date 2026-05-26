from decimal import Decimal

from sqlalchemy import exists, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from api.enums.enums_v1 import OrderStates, UserRoles
from api.exceptions import (
    MonthOrdersLimitExceededError,
    OrderNotFoundError,
    UserNotFoundError,
    ValidationError,
)
from api.utils.help_orders_method import check_user_month_orders_limit
from api.utils.help_orders_method import generate_order_link, generate_order_slug
from database.config import AsyncSessionLocal
from database.models.orders import Order, OrderStatusHistory
from database.models.users import User


ACTIVE_ORDER_STATUSES = (
    OrderStates.AWAITING_PERFORMER.value,
    OrderStates.AWAITING_PAYMENT.value,
    OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
    OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
    OrderStates.AWAITING_CONFLICT.value,
    OrderStates.OPEN_CONFLICT.value,
)


async def create_order(
    client_id: int,
    title: str,
    conditions: str,
    result_requirements: str,
    violation_proof_requirements: str,
    price: Decimal,
) -> Order:
    
    """
    Метод создает ордер и проверяет месячный лимит для пользователя, установленный в .env
    Состояние дублируется в таблицу историй состояний сделки.
    
    """

    while True:
        async with AsyncSessionLocal() as session:
            try:
                async with session.begin():
                    user_exists = await session.scalar(
                        select(exists().where(User.id == client_id))
                    )
                    if not user_exists:
                        raise UserNotFoundError()

                    limit_check = await check_user_month_orders_limit(session, client_id, price)
                    if not limit_check["success"]:
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
                    return order
            except IntegrityError as exc:
                if "uq_orders_slug" in str(exc.orig):
                    continue
                raise


async def get_order_link(order_id: int) -> str:

    """
    Метод получает slug ордера и генерирует полноценную ссылку для перехода на страницу с информацией о сделке
    
    """

    async with AsyncSessionLocal() as session:
        slug = await session.scalar(select(Order.slug).where(Order.id == order_id))
        if slug is None:
            raise OrderNotFoundError()
        return generate_order_link(slug)


async def get_order_by_slug(slug: str) -> Order:
    """Достаем информацию об ордере по слагу"""
    async with AsyncSessionLocal() as session:
        order = await session.scalar(select(Order).where(Order.slug == slug))
        if order is None:
            raise OrderNotFoundError()
        return order


async def get_active_orders_by_role(role: UserRoles | str) -> list[Order]:
    """Получаем список активных ордеров в зависимости от роли пользователя"""
    role_value = role.value if isinstance(role, UserRoles) else role
    if role_value not in {UserRoles.CLIENT.value, UserRoles.PERFORMER.value}:
        raise ValidationError()

    async with AsyncSessionLocal() as session:
        query = select(Order).where(Order.status.in_(ACTIVE_ORDER_STATUSES))
        if role_value == UserRoles.PERFORMER.value:
            query = query.where(
                or_(
                    Order.status == OrderStates.AWAITING_PERFORMER.value,
                    Order.performer_id.is_not(None),
                )
            )

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

            current_status = await session.scalar(
                select(Order.status).where(Order.id == order_id).with_for_update()
            )
            if current_status is None:
                raise OrderNotFoundError()

            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(
                    performer_id=performer_id,
                    status=OrderStates.AWAITING_PAYMENT.value,
                )
            )
            await session.execute(
                insert(OrderStatusHistory).values(
                    order_id=order_id,
                    old_status=(
                        current_status.value
                        if isinstance(current_status, OrderStates)
                        else current_status
                    ),
                    new_status=OrderStates.AWAITING_PAYMENT.value,
                    changed_by_user_id=performer_id,
                )
            )


async def payment_order(order_id: int, client_id: int) -> None:
    """Переводим сделку в состояние после оплаты и ожидания подтверждения со стороны исполнителя"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            client_exists = await session.scalar(
                select(exists().where(User.id == client_id))
            )
            if not client_exists:
                raise UserNotFoundError()

            current_status = await session.scalar(
                select(Order.status).where(Order.id == order_id).with_for_update()
            )
            if current_status is None:
                raise OrderNotFoundError()

            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(status=OrderStates.AWAITING_PERFORMER_CONFIRMATION.value)
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
