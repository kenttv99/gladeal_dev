from __future__ import annotations

from urllib.parse import urlencode

from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_BASE_URL, PAYGINE_SECTOR
from api.schemas.schemas_v1 import GenerateWithdrowLinkRequest


GENERATE_WITHDROW_LINK_ENDPOINT = "/webapi/b2puser/sd-services/SDPayOutPage"
GENERATE_WITHDROW_LINK_SIGNATURE_FIELDS = ("sector", "id")


async def create_withdrow_link(
    data: GenerateWithdrowLinkRequest,
) -> str:
    """Генерируем ссылку для получения средств исполнителем."""
    payload = build_generate_withdrow_link_payload(data)
    query = urlencode(payload)
    return f"{PAYGINE_BASE_URL.rstrip('/')}{GENERATE_WITHDROW_LINK_ENDPOINT}?{query}"


def build_generate_withdrow_link_payload(
    data: GenerateWithdrowLinkRequest,
) -> dict[str, object]:
    """Собираем query params для SDComplete."""
    payload = {
        "sector": PAYGINE_SECTOR,
        "id": data.paygine_order_id,
    }
    payload["signature"] = build_signature(
        payload[field] for field in GENERATE_WITHDROW_LINK_SIGNATURE_FIELDS
    )
    return payload
