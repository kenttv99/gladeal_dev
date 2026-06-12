import uvicorn
from fastapi import FastAPI

from api.exceptions import register_exception_handlers
from api.webhooks.v1.order_status_webhook import router as order_status_webhook_router
from api.webhooks.v1.redirect_after_payments_webhook import (
    router as redirect_after_payments_webhook_router,
)


app = FastAPI(
    title="GLADEAL Payments API",
    description="API для платежных callback-уведомлений",
    version="1.0.0",
)

register_exception_handlers(app)

app.include_router(
    order_status_webhook_router,
    prefix="/v1/paygine",
    tags=["Paygine webhooks"],
)
app.include_router(
    redirect_after_payments_webhook_router,
    prefix="/v1/paygine/redirect",
    tags=["Paygine redirects"],
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
