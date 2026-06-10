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
from api.schemas.schemas_v1 import CompletePaymentedDealRequest


REAL_COMPLETE_PAYMENTED_DEAL_DATA = {
    "paygine_payment_operation_id": 13130110,
}


class CompletePaymentedDealIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_complete_paymented_deal_payload_uses_payment_operation_id(self):
        payment_data = CompletePaymentedDealRequest(**REAL_COMPLETE_PAYMENTED_DEAL_DATA)
        payload = build_complete_paymented_deal_payload(payment_data)
        expected_signature = build_signature(
            (PAYGINE_SECTOR, payment_data.paygine_payment_operation_id)
        )

        self.assertEqual(payload["id"], payment_data.paygine_payment_operation_id)
        self.assertEqual(payload["signature"], expected_signature)

    async def test_complete_paymented_deal_returns_readable_paygine_response(self):
        """Переводим оплаченную сделку в ПЦ в COMPLETE."""
        payment_data = CompletePaymentedDealRequest(**REAL_COMPLETE_PAYMENTED_DEAL_DATA)

        try:
            response = await complete_paymented_deal(payment_data)
        except PaymentInvalidProviderResponseError as exc:
            self.fail(f"Paygine complete response parse error: {exc.details}")

        print(json.dumps(response, ensure_ascii=False, indent=2))

        self.assertIn("root_tag", response)
        self.assertIn("data", response)
        self.assertIsInstance(response["root_tag"], str)


if __name__ == "__main__":
    unittest.main()
