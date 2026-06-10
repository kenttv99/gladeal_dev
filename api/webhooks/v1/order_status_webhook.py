import logging

from fastapi import APIRouter, Request

from api.utils.order_status_webhook_methods import (
    handle_order_status_webhook,
    read_order_status_webhook_payload,
)


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook_order_status")
async def webhook_order_status(request: Request) -> dict[str, object]:
    payload = await read_order_status_webhook_payload(request)
    print(payload)
    logger.info("Received Paygine order status webhook: %s", payload)
    return await handle_order_status_webhook(payload)
