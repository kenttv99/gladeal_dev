from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, exists
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import MONTH_SUM_LIMIT_PER_USER
from database.models.orders import Order

from secrets import token_urlsafe

async def generate_order_slug(session: AsyncSession) -> str:
    while True:
        slug = token_urlsafe(16)
        slug_exists = await session.scalar(select(exists().where(Order.slug == slug)))
        if not slug_exists:
            return slug



async def check_user_month_orders_limit(
    session: AsyncSession,
    user_id: int,
    price: Decimal,
) -> dict[str, bool | str]:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (
        month_start.replace(year=month_start.year + 1, month=1)
        if month_start.month == 12
        else month_start.replace(month=month_start.month + 1)
    )

    month_sum = await session.scalar(
        select(func.coalesce(func.sum(Order.price), 0)).where(
            Order.client_id == user_id,
            Order.created_at >= month_start,
            Order.created_at < next_month,
        )
    )
    delta = Decimal(month_sum) + price - Decimal(MONTH_SUM_LIMIT_PER_USER)

    return {
        "success": delta <= 0,
        "delta": str(max(delta, Decimal("0"))),
    }
