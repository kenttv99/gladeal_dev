from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from api.exceptions import PhoneNumberAlreadyExistsError
from database.config import AsyncSessionLocal
from database.models.users import User


async def register_user(
    first_name: str,
    last_name: str,
    phone_number: str,
    ppd: bool = False,
) -> User:
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
