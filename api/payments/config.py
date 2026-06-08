from os import getenv
from pathlib import Path
from decimal import Decimal

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env.payments")

PAYGINE_BASE_URL = getenv("PAYGINE_BASE_URL")
PAYGINE_SECTOR = getenv("PAYGINE_SECTOR")
PAYGINE_SIGNATURE_PASSWORD = getenv("PAYGINE_SIGNATURE_PASSWORD")
SR_REF = getenv("SR_REF")
DEAL_FEE_PERCENT = getenv("DEAL_FEE_PERCENT")
PAYGINE_REQUEST_TIMEOUT_SECONDS = 30

if not PAYGINE_SECTOR:
    raise RuntimeError("PAYGINE_SECTOR is not set")

if not PAYGINE_SIGNATURE_PASSWORD:
    raise RuntimeError("PAYGINE_SIGNATURE_PASSWORD is not set")

if not SR_REF:
    raise RuntimeError("SR_REF is not set")

if not DEAL_FEE_PERCENT:
    raise RuntimeError("DEAL_FEE_PERCENT is not set")

if not PAYGINE_BASE_URL:
    raise RuntimeError("PAYGINE_BASE_URL is not set")

PAYGINE_BASE_URL = str(PAYGINE_BASE_URL)
PAYGINE_SECTOR = str(PAYGINE_SECTOR)
PAYGINE_SIGNATURE_PASSWORD = str(PAYGINE_SIGNATURE_PASSWORD)
SR_REF = str(SR_REF)
DEAL_FEE_PERCENT = Decimal(DEAL_FEE_PERCENT)
