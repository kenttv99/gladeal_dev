from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from api.payments.auth_methods import build_signature, is_valid_signature
from api.payments.config import (
    PAYGINE_BASE_URL,
    PAYGINE_REQUEST_TIMEOUT_SECONDS,
    PAYGINE_SECTOR,
)


REGISTER_DEAL_ENDPOINT = "/webapi/Register"
REGISTER_DEAL_SIGNATURE_FIELDS = ("sector", "amount", "currency")


@dataclass(frozen=True)
class DealParticipant:
    client_ref: str
    email: str | None = None
    phone: str | None = None


@dataclass(frozen=True)
class RegisterDealRequest:
    customer: DealParticipant
    performer: DealParticipant
    amount: int
    reference: str
    description: str
    currency: int = 643
    fee: int | None = None
    url: str | None = None
    failurl: str | None = None
    life_period: int | None = None
    sd_ref: str | None = None
    notify_url: str | None = None
    mode: int = 0


@dataclass(frozen=True)
class RegisterDealResponse:
    paygine_order_id: str | None
    signature: str
    customer_ref: str
    performer_ref: str
    response_data: dict[str, str]
    raw_response: str


class RegisterDealError(RuntimeError):
    pass


def build_register_deal_payload(data: RegisterDealRequest) -> dict[str, object]:
    payload = {
        "sector": PAYGINE_SECTOR,
        "amount": data.amount,
        "currency": data.currency,
        "reference": data.reference,
        "description": data.description,
        "payer_id": data.customer.client_ref,
        "email": data.customer.email,
        "phone": data.customer.phone,
        "fee": data.fee,
        "url": data.url,
        "failurl": data.failurl,
        "life_period": data.life_period,
        "sd_ref": data.sd_ref,
        "notify_url": data.notify_url,
        "mode": data.mode,
    }
    payload["signature"] = build_signature(
        payload[field] for field in REGISTER_DEAL_SIGNATURE_FIELDS
    )
    return {key: value for key, value in payload.items() if value is not None}


async def send_register_deal_request(
    data: RegisterDealRequest,
) -> RegisterDealResponse:
    payload = build_register_deal_payload(data)
    raw_response = await asyncio.to_thread(_post_register_deal, payload)
    response_data = _parse_response(raw_response)
    paygine_order_id = response_data.get("id") or (
        raw_response.strip() if data.mode == 1 else None
    )

    if not paygine_order_id:
        raise RegisterDealError(raw_response)

    return RegisterDealResponse(
        paygine_order_id=paygine_order_id,
        signature=str(payload["signature"]),
        customer_ref=data.customer.client_ref,
        performer_ref=data.performer.client_ref,
        response_data=response_data,
        raw_response=raw_response,
    )


def _post_register_deal(payload: dict[str, object]) -> str:
    request = Request(
        f"{PAYGINE_BASE_URL}{REGISTER_DEAL_ENDPOINT}",
        data=urlencode(payload).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
    )
    with urlopen(request, timeout=PAYGINE_REQUEST_TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _parse_response(raw_response: str) -> dict[str, str]:
    if not raw_response.lstrip().startswith("<"):
        return {}

    root = ElementTree.fromstring(raw_response)
    data = {child.tag: child.text or "" for child in root}

    if root.tag.lower() != "order":
        raise RegisterDealError(raw_response)

    if data.get("signature") and not is_valid_signature(
        (child.text or "" for child in root if child.tag != "signature"),
        data["signature"],
    ):
        raise RegisterDealError("Invalid Paygine response signature")

    return data
