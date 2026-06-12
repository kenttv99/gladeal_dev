from __future__ import annotations

import asyncio
import logging

from database.config import AsyncSessionLocal
from workers.utils.order_expire_methods import WORKER_SLEEP_SECONDS, process_expired_orders


logger = logging.getLogger(__name__)


async def run_worker() -> None:
    """Мейн воркер."""
    while True:
        try:
            async with AsyncSessionLocal() as session:
                processed = await process_expired_orders(session)
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
