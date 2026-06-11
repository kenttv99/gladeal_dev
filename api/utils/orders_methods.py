from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from api.enums.enums_v1 import OrderStates, UserRoles
from api.exceptions import (
    OrderAlreadyAcceptedError,
    OrderNotFoundError,
    OrderSelfExecutionForbiddenError,
    ValidationError,
)
from api.payments.payments_methods import cancle_unpayment_deal, register_deposit_deal
from api.schemas.schemas_v1 import CreateOrderResponse, OrderInfoResponse, RegisterDepositDealPaymentRequest
from api.utils.help_orders_method import (
    ACTIVE_ORDER_STATUSES,
    CLOSED_ORDER_STATUSES,
    add_order_status_history,
    create_order_payment_data,
    create_order_record,
    delete_order_record,
    ensure_registered_order_payment_status,
    ensure_user_exists,
    generate_order_link,
    get_softdecline_payment_operation_id,
    order_status_value,
    order_status_values,
    set_softdeclined_order_status,
)
from database.config import AsyncSessionLocal
from database.models.orders import Order
from database.models.payments import OrderPaymentData


async def create_order(
    client_id: int,
    customer_email: str,
    title: str,
    conditions: str,
    result_requirements: str,
    violation_proof_requirements: str,
    price: Decimal,
    expire_in: datetime,
) -> CreateOrderResponse:
    """
    Метод создает ордер и проверяет месячный лимит для пользователя, установленный в .env, производит запрос к платежной системе, получает ответ и записывает данные в таблицы.
    Состояние дублируется в таблицу историй состояний сделки.

    """

    while True:
        async with AsyncSessionLocal() as session:
            try:
                async with session.begin():
                    order, customer_phone = await create_order_record(
                        session=session,
                        client_id=client_id,
                        title=title,
                        conditions=conditions,
                        result_requirements=result_requirements,
                        violation_proof_requirements=violation_proof_requirements,
                        price=price,
                        expire_in=expire_in,
                    )
                break
            except IntegrityError as exc:
                if "uq_orders_slug" in str(exc.orig):
                    continue
                raise

    try:
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
    except Exception:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await delete_order_record(session, order.id, client_id)
        raise

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await create_order_payment_data(
                session,
                order.id,
                customer_email,
                payment_result.payment_values.model_dump(),
            )
    return CreateOrderResponse(
        **OrderInfoResponse.model_validate(order).model_dump(),
        service_fee_amount=payment_result.payment_values.service_fee_amount,
    )


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


async def get_order_payment_operation_id(order_id: int, client_id: int) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OrderPaymentData.paygine_payment_operation_id, OrderPaymentData.status)
            .join(Order, Order.id == OrderPaymentData.order_id)
            .where(Order.id == order_id, Order.client_id == client_id)
        )
        row = result.one_or_none()
        if row is None or row[0] is None:
            raise OrderNotFoundError()
        ensure_registered_order_payment_status(row[1])
        return int(row[0])


async def get_order_payout_operation_id(order_id: int, performer_id: int) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OrderPaymentData.paygine_payout_operation_id, OrderPaymentData.status)
            .join(Order, Order.id == OrderPaymentData.order_id)
            .where(Order.id == order_id, Order.performer_id == performer_id)
        )
        row = result.one_or_none()
        if row is None or row[0] is None:
            raise OrderNotFoundError()
        ensure_registered_order_payment_status(row[1])
        return int(row[0])


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
            await ensure_user_exists(session, performer_id)

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
            current_status_value = order_status_value(current_status)
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
                    **order_status_values(OrderStates.AWAITING_PAYMENT.value),
                )
            )
            await add_order_status_history(
                session,
                order_id,
                current_status_value,
                OrderStates.AWAITING_PAYMENT.value,
                performer_id,
            )


async def performer_confirm_order(order_id: int, performer_id: int) -> None:
    """Переводим сделку в состояние ожидания подтверждения заказчиком"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await ensure_user_exists(session, performer_id)

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
                .values(**order_status_values(OrderStates.AWAITING_CLIENT_CONFIRMATION.value))
            )
            await add_order_status_history(
                session,
                order_id,
                current_status,
                OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
                performer_id,
            )


async def client_confirm_order(order_id: int, client_id: int) -> None:
    """Переводим сделку в состояние успешного завершения и ожидания получения выплаты исполнителем"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await ensure_user_exists(session, client_id)

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
                .values(**order_status_values(OrderStates.AWAITING_PERFORMER_PAYOUT.value))
            )
            await add_order_status_history(
                session,
                order_id,
                current_status,
                OrderStates.AWAITING_PERFORMER_PAYOUT.value,
                client_id,
            )


async def performer_order_payout(order_id: int, performer_id: int) -> None:
    """Переводим сделку в состояние успешного завершения после выплаты исполнителю"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await ensure_user_exists(session, performer_id)

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
            current_status_value = order_status_value(current_status)
            if current_status_value != OrderStates.AWAITING_PERFORMER_PAYOUT.value:
                raise ValidationError()

            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(**order_status_values(OrderStates.SUCCESSFUL_COMPLETION.value))
            )
            await add_order_status_history(
                session,
                order_id,
                current_status_value,
                OrderStates.SUCCESSFUL_COMPLETION.value,
                performer_id,
            )


async def performer_decline_order(order_id: int, performer_id: int) -> None:
    """Переводим сделку в состояние неуспешного завершения по отказу исполнителя"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await ensure_user_exists(session, performer_id)

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
                .values(**order_status_values(OrderStates.UNSUCCESSFUL_COMPLETION.value))
            )
            await add_order_status_history(
                session,
                order_id,
                current_status,
                OrderStates.UNSUCCESSFUL_COMPLETION.value,
                performer_id,
            )


async def client_softdecline_order(order_id: int, client_id: int) -> None:
    """Переводим сделку в неуспешное завершение, если исполнитель еще не принял ее"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            payment_operation_id, current_status = await get_softdecline_payment_operation_id(
                session,
                order_id,
                client_id,
            )
            await cancle_unpayment_deal(payment_operation_id)
            await set_softdeclined_order_status(session, order_id, current_status, client_id)


async def client_harddecline_order(order_id: int, client_id: int) -> None:
    """Переводим сделку в состояние ожидания подтверждения отказа исполнителем"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await ensure_user_exists(session, client_id)

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
                .values(**order_status_values(OrderStates.AWAITING_CONFLICT.value))
            )
            await add_order_status_history(
                session,
                order_id,
                current_status,
                OrderStates.AWAITING_CONFLICT.value,
                client_id,
            )


async def performer_conflict_order(order_id: int, performer_id: int) -> None:
    """Переводим сделку в состояние открытого спора исполнителем"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await ensure_user_exists(session, performer_id)

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
                .values(**order_status_values(OrderStates.OPEN_CONFLICT.value))
            )
            await add_order_status_history(
                session,
                order_id,
                current_status,
                OrderStates.OPEN_CONFLICT.value,
                performer_id,
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
