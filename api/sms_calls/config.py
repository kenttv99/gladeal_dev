from os import getenv
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env.sms_calls")

PROSTO_SMS_BASE_URL = getenv("PROSTO_SMS_BASE_URL")
PROSTO_SMS_API_KEY = getenv("PROSTO_SMS_API_KEY")
SMS_CALLS_REDIS_URL = getenv("SMS_CALLS_REDIS_URL")
SMS_CALLS_CODE_TTL_SECONDS = getenv("SMS_CALLS_CODE_TTL_SECONDS")
PROSTO_SMS_REQUEST_TIMEOUT_SECONDS = 30
PROSTO_SMS_SENDER_NAME = "Gladeal"
PROSTO_SMS_PRIORITY = 1

if not PROSTO_SMS_BASE_URL:
    raise RuntimeError("PROSTO_SMS_BASE_URL is not set")

if not PROSTO_SMS_API_KEY:
    raise RuntimeError("PROSTO_SMS_API_KEY is not set")

if not SMS_CALLS_REDIS_URL:
    raise RuntimeError("SMS_CALLS_REDIS_URL is not set")

if not SMS_CALLS_CODE_TTL_SECONDS:
    raise RuntimeError("SMS_CALLS_CODE_TTL_SECONDS is not set")

PROSTO_SMS_BASE_URL = str(PROSTO_SMS_BASE_URL).strip()
PROSTO_SMS_API_KEY = str(PROSTO_SMS_API_KEY)
SMS_CALLS_REDIS_URL = str(SMS_CALLS_REDIS_URL)
SMS_CALLS_CODE_TTL_SECONDS = int(SMS_CALLS_CODE_TTL_SECONDS)
