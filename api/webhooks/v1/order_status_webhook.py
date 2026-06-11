import logging

from fastapi import APIRouter, Request

from api.utils.order_status_webhook_methods import (
    get_order_status_webhook_state,
    read_order_status_webhook_payload,
    update_order_payment_status_from_webhook,
)


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook_order_status")
async def webhook_order_status(request: Request) -> dict[str, object]:
    payload = await read_order_status_webhook_payload(request)
    logger.info("Received Paygine order status webhook: %s", payload)
    order_state = get_order_status_webhook_state(payload)
    await update_order_payment_status_from_webhook(payload, order_state)
    return {"status": "accepted", "order_state": order_state}
