from os import getenv
from decimal import Decimal

from dotenv import load_dotenv


load_dotenv()

JWT_SECRET_KEY = getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = getenv("JWT_ALGORITHM")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
MONTH_SUM_LIMIT_PER_USER = getenv("MONTH_SUM_LIMIT_PER_USER")

if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is not set")

if not JWT_ALGORITHM:
    raise RuntimeError("JWT_ALGORITHM is not set")

if not JWT_ACCESS_TOKEN_EXPIRE_MINUTES:
    raise RuntimeError("JWT_ACCESS_TOKEN_EXPIRE_MINUTES is not set")

if not MONTH_SUM_LIMIT_PER_USER:
    raise RuntimeError("MONTH_SUM_LIMIT_PER_USER is not set")

JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
MONTH_SUM_LIMIT_PER_USER = Decimal(MONTH_SUM_LIMIT_PER_USER)
