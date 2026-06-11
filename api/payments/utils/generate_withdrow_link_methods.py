from __future__ import annotations

from urllib.parse import urlencode

from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_BASE_URL, PAYGINE_SECTOR, SR_REF


GENERATE_WITHDROW_LINK_ENDPOINT = "/webapi/b2puser/sd-services/SDPayOutPage"
GENERATE_WITHDROW_LINK_SIGNATURE_FIELDS = ("sector", "id", "sd_ref")


async def create_withdrow_link(
    paygine_payout_operation_id: int,
) -> str:
    """Генерируем ссылку для получения средств исполнителем."""
    payload = build_generate_withdrow_link_payload(paygine_payout_operation_id)
    query = urlencode(payload)
    return f"{PAYGINE_BASE_URL.rstrip('/')}{GENERATE_WITHDROW_LINK_ENDPOINT}?{query}"


def build_generate_withdrow_link_payload(
    paygine_payout_operation_id: int,
) -> dict[str, object]:
    """Собираем query params для SDPayOutPage."""
    payload = {
        "sector": PAYGINE_SECTOR,
        "id": paygine_payout_operation_id,
        "sd_ref": SR_REF,
    }
    payload["signature"] = build_signature(
        payload[field] for field in GENERATE_WITHDROW_LINK_SIGNATURE_FIELDS
    )
    return payload
