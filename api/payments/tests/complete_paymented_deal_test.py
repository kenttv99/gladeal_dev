from __future__ import annotations

import json
import unittest

from api.exceptions import PaymentInvalidProviderResponseError
from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_SECTOR
from api.payments.payments_methods import complete_paymented_deal
from api.payments.utils.complete_paymented_deal_methods import (
    build_complete_paymented_deal_payload,
)


REAL_COMPLETE_PAYMENTED_DEAL_DATA = {
    "paygine_payment_operation_id": 13130110,
}


class CompletePaymentedDealIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_complete_paymented_deal_payload_uses_payment_operation_id(self):
        operation_id = REAL_COMPLETE_PAYMENTED_DEAL_DATA["paygine_payment_operation_id"]
        payload = build_complete_paymented_deal_payload(operation_id)
        expected_signature = build_signature(
            (PAYGINE_SECTOR, operation_id)
        )

        self.assertEqual(payload["id"], operation_id)
        self.assertEqual(payload["signature"], expected_signature)

    async def test_complete_paymented_deal_returns_readable_paygine_response(self):
        """Переводим оплаченную сделку в ПЦ в COMPLETE."""
        operation_id = REAL_COMPLETE_PAYMENTED_DEAL_DATA["paygine_payment_operation_id"]

        try:
            response = await complete_paymented_deal(operation_id)
        except PaymentInvalidProviderResponseError as exc:
            self.fail(f"Paygine complete response parse error: {exc.details}")

        print(json.dumps(response, ensure_ascii=False, indent=2))

        self.assertIn("root_tag", response)
        self.assertIn("data", response)
        self.assertIsInstance(response["root_tag"], str)


if __name__ == "__main__":
    unittest.main()
