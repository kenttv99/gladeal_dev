from __future__ import annotations

import json
import unittest
from urllib.parse import parse_qs, urlparse

from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_BASE_URL, PAYGINE_SECTOR, SR_REF
from api.payments.payments_methods import generate_payment_link
from api.payments.utils.generate_payment_link_methods import (
    GENERATE_PAYMENT_LINK_ENDPOINT,
)
from api.schemas.schemas_v1 import GeneratePaymentLinkRequest


REAL_GENERATE_PAYMENT_LINK_DATA = {
    "paygine_payment_operation_id": 13140587,
}


class GeneratePaymentLinkIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_generate_payment_link_returns_paygine_url(self):
        """Генерируем ссылку на оплату зарегистрированной сделки в ПЦ."""
        payment_data = GeneratePaymentLinkRequest(**REAL_GENERATE_PAYMENT_LINK_DATA)

        payment_link = await generate_payment_link(payment_data)
        parsed_url = urlparse(payment_link)
        parsed_query = parse_qs(parsed_url.query)
        expected_signature = build_signature(
            (PAYGINE_SECTOR, payment_data.paygine_payment_operation_id, SR_REF)
        )

        print(json.dumps({"payment_link": payment_link}, ensure_ascii=False, indent=2))

        self.assertTrue(
            payment_link.startswith(
                f"{PAYGINE_BASE_URL.rstrip('/')}{GENERATE_PAYMENT_LINK_ENDPOINT}?"
            )
        )
        self.assertEqual(parsed_query["sector"], [PAYGINE_SECTOR])
        self.assertEqual(
            parsed_query["id"],
            [str(payment_data.paygine_payment_operation_id)],
        )
        self.assertEqual(parsed_query["sd_ref"], [SR_REF])
        self.assertEqual(parsed_query["signature"], [expected_signature])


if __name__ == "__main__":
    unittest.main()
