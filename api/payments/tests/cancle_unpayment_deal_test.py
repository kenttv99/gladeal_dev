from __future__ import annotations

import json
import unittest

from api.exceptions import PaymentInvalidProviderResponseError
from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_SECTOR
from api.payments.payments_methods import cancle_unpayment_deal
from api.payments.utils.cancle_unpayment_deal_methods import (
    EXPIRED_ORDER_STATE,
    build_cancle_unpayment_deal_payload,
)


REAL_CANCLE_UNPAYMENT_DEAL_DATA = {
    "paygine_payment_operation_id": 13098226,
}


class CancleUnpaymentDealIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_cancle_unpayment_deal_payload_uses_payment_operation_id(self):
        operation_id = REAL_CANCLE_UNPAYMENT_DEAL_DATA["paygine_payment_operation_id"]
        payload = build_cancle_unpayment_deal_payload(operation_id)
        expected_signature = build_signature(
            (PAYGINE_SECTOR, operation_id, EXPIRED_ORDER_STATE)
        )

        self.assertEqual(payload["id"], operation_id)
        self.assertEqual(payload["signature"], expected_signature)

    async def test_cancle_unpayment_deal_returns_readable_paygine_response(self):
        """Переводим существующий заказ в ПЦ в EXPIRED."""
        operation_id = REAL_CANCLE_UNPAYMENT_DEAL_DATA["paygine_payment_operation_id"]

        try:
            response = await cancle_unpayment_deal(operation_id)
        except PaymentInvalidProviderResponseError as exc:
            self.fail(f"Paygine cancle response parse error: {exc.details}")

        print(json.dumps(response, ensure_ascii=False, indent=2))

        self.assertIn("root_tag", response)
        self.assertIn("data", response)
        self.assertIsInstance(response["root_tag"], str)


if __name__ == "__main__":
    unittest.main()
