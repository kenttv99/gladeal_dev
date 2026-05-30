from decimal import Decimal
from os import getenv
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

JWT_SECRET_KEY = getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = getenv("JWT_ALGORITHM")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
MONTH_SUM_LIMIT_PER_USER = getenv("MONTH_SUM_LIMIT_PER_USER")
BASE_SITE_LINK = getenv("BASE_SITE_LINK")
EXPIRE_TIME_TO_COMNFIRM_MINUTES = getenv("EXPIRE_TIME_TO_COMNFIRM_MINUTES")

if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is not set")

if not JWT_ALGORITHM:
    raise RuntimeError("JWT_ALGORITHM is not set")

if not JWT_ACCESS_TOKEN_EXPIRE_MINUTES:
    raise RuntimeError("JWT_ACCESS_TOKEN_EXPIRE_MINUTES is not set")

if not MONTH_SUM_LIMIT_PER_USER:
    raise RuntimeError("MONTH_SUM_LIMIT_PER_USER is not set")

if not BASE_SITE_LINK:
    raise RuntimeError("BASE_SITE_LINK is not set")

if not EXPIRE_TIME_TO_COMNFIRM_MINUTES:
    raise RuntimeError("EXPIRE_TIME_TO_COMNFIRM_MINUTES is not set")

JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
JWT_ALGORITHM = str(JWT_ALGORITHM)
JWT_SECRET_KEY = str(JWT_SECRET_KEY)
MONTH_SUM_LIMIT_PER_USER = Decimal(MONTH_SUM_LIMIT_PER_USER)
BASE_SITE_LINK = str(BASE_SITE_LINK)
EXPIRE_TIME_TO_COMNFIRM_MINUTES = Decimal(EXPIRE_TIME_TO_COMNFIRM_MINUTES)
