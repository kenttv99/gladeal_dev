from os import getenv
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env.payments")

PAYGINE_BASE_URL = "https://test.paygine.com"
PAYGINE_SECTOR = getenv("PAYGINE_SECTOR")
PAYGINE_SIGNATURE_PASSWORD = getenv("PAYGINE_SIGNATURE_PASSWORD")
PAYGINE_REQUEST_TIMEOUT_SECONDS = 30

if not PAYGINE_SECTOR:
    raise RuntimeError("PAYGINE_SECTOR is not set")

if not PAYGINE_SIGNATURE_PASSWORD:
    raise RuntimeError("PAYGINE_SIGNATURE_PASSWORD is not set")

PAYGINE_SECTOR = str(PAYGINE_SECTOR)
PAYGINE_SIGNATURE_PASSWORD = str(PAYGINE_SIGNATURE_PASSWORD)
