from decimal import Decimal

from sqlalchemy import exists, insert, select
from sqlalchemy.exc import IntegrityError

from api.enums.enums_v1 import OrderStates
from api.exceptions import MonthOrdersLimitExceededError, UserNotFoundError
from api.utils.help_orders_method import check_user_month_orders_limit
from api.utils.help_orders_method import generate_order_slug
from database.config import AsyncSessionLocal
from database.models.orders import Order, OrderStatusHistory
from database.models.users import User


async def create_order(
    client_id: int,
    title: str,
    conditions: str,
    result_requirements: str,
    violation_proof_requirements: str,
    price: Decimal,
) -> Order:
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
