import logging

from fastapi import APIRouter, Request

from api.enums.enums_v1 import OrderPaymentStates
from api.utils.order_status_webhook_methods import (
    authorize_order_payment_from_webhook,
    get_order_status_webhook_state,
    read_order_status_webhook_payload,
)


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook_order_status")
async def webhook_order_status(request: Request) -> dict[str, object]:
    payload = await read_order_status_webhook_payload(request)
    logger.info("Received Paygine order status webhook: %s", payload)
    order_state = get_order_status_webhook_state(payload)
    if order_state == OrderPaymentStates.AUTHORIZED.value:
        await authorize_order_payment_from_webhook(payload)
    return {"status": "accepted", "order_state": order_state}
