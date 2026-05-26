from secrets import token_urlsafe

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.orders import Order


async def generate_order_slug(session: AsyncSession) -> str:
    while True:
        slug = token_urlsafe(16)
        slug_exists = await session.scalar(select(exists().where(Order.slug == slug)))
        if not slug_exists:
            return slug
