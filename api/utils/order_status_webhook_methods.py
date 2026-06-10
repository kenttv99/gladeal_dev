from __future__ import annotations

import json
from urllib.parse import parse_qsl

from fastapi import Request


async def read_order_status_webhook_payload(request: Request) -> dict[str, object]:
    """Читаем callback payload Paygine без бизнес-обработки."""
    body = await request.body()
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip()

    if content_type == "application/json":
        return json.loads(body or b"{}")
    if content_type == "application/x-www-form-urlencoded":
        return dict(parse_qsl(body.decode("utf-8"), keep_blank_values=True))
    return {"raw": body.decode("utf-8")}


async def handle_order_status_webhook(payload: dict[str, object]) -> dict[str, object]:
    return payload
