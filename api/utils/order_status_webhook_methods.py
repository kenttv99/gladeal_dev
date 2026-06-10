from __future__ import annotations

import json
from urllib.parse import parse_qsl

from fastapi import Request

from api.payments.utils.xml_response_parser import parse_paygine_response


async def read_order_status_webhook_payload(request: Request) -> dict[str, object]:
    """Читаем callback payload Paygine без бизнес-обработки."""
    body = await request.body()
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
    raw_body = body.decode("utf-8")

    if content_type == "application/json":
        return json.loads(body or b"{}")
    if content_type == "application/x-www-form-urlencoded":
        return dict(parse_qsl(raw_body, keep_blank_values=True))
    if content_type in {"application/xml", "text/xml"} or raw_body.strip().startswith("<"):
        return parse_paygine_response(raw_body)
    return {"raw": raw_body}


async def handle_order_status_webhook(payload: dict[str, object]) -> dict[str, object]:
    return payload
