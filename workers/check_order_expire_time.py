from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update

from api.config import EXPIRE_TIME_TO_COMNFIRM_MINUTES
from api.enums.enums_v1 import OrderStates
from api.exceptions import OrderNotFoundError, ValidationError
from api.utils.orders_methods import expire_order
from database.config import AsyncSessionLocal
from database.models.orders import Order


EXPIRED_ORDER_BATCH_SIZE = 1000
WORKER_SLEEP_SECONDS = 60

logger = logging.getLogger(__name__)


def _worker_check_allowed(now: datetime):
    """Проверяем, можно ли воркеру повторно брать сделку в обработку."""
    check_cutoff = now - timedelta(seconds=WORKER_SLEEP_SECONDS)
    return or_(Order.checked_by_worker_at.is_(None), Order.checked_by_worker_at <= check_cutoff)


async def _claim_order_ids(*conditions, order_by, checked_at: datetime, limit: int) -> list[int]:
    """Атомарно выбираем сделки по условиям и фиксирует время проверки воркером."""
    candidate_ids = (
        select(Order.id)
        .where(*conditions, _worker_check_allowed(checked_at))
        .order_by(*order_by, Order.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
        .cte("candidate_orders")
    )

    async with AsyncSessionLocal() as session:
        async with session.begin():
            return list(
                (
                    await session.scalars(
                        update(Order)
                        .where(Order.id.in_(select(candidate_ids.c.id)))
                        .values(checked_by_worker_at=checked_at)
                        .returning(Order.id)
                    )
                ).all()
            )


async def claim_expired_order_ids(limit: int = EXPIRED_ORDER_BATCH_SIZE) -> dict[str, list[int]]:
    """Получаем IDS сделок для отмены и подтверждения."""
    checked_at = datetime.now(timezone.utc)
    confirm_cutoff = checked_at - timedelta(minutes=float(EXPIRE_TIME_TO_COMNFIRM_MINUTES))

    return {
        "cancle": await _claim_order_ids(
            Order.status == OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
            Order.expire_in <= checked_at,
            order_by=(Order.expire_in,),
            checked_at=checked_at,
            limit=limit,
        ),
        "confirm": await _claim_order_ids(
            Order.status == OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
            Order.completed_at.is_not(None),
            Order.completed_at <= confirm_cutoff,
            order_by=(Order.completed_at,),
            checked_at=checked_at,
            limit=limit,
        ),
    }


async def process_expired_orders() -> dict[str, int]:
    """Обрабатываем просроченные сделки батчами и возвращаем количество изменений."""
    processed = {"cancle": 0, "confirm": 0}

    while True:
        expired_order_ids = await claim_expired_order_ids()
        if not any(expired_order_ids.values()):
            return processed

        for act, order_ids in expired_order_ids.items():
            for order_id in order_ids:
                try:
                    await expire_order(order_id, act)
                except (OrderNotFoundError, ValidationError):
                    logger.info("Skipped expired order %s with action %s", order_id, act)
                else:
                    processed[act] += 1


async def run_worker() -> None:
    """Мейн воркер"""
    while True:
        try:
            processed = await process_expired_orders()
            logger.info(
                "Processed expired orders: cancle=%s confirm=%s",
                processed["cancle"],
                processed["confirm"],
            )
        except Exception:
            logger.exception("Order expire worker iteration failed")

        await asyncio.sleep(WORKER_SLEEP_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
