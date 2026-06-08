from __future__ import annotations

import json
import unittest

from api.exceptions import PaymentInvalidProviderResponseError
from api.payments.payments_methods import complete_paymented_deal
from api.schemas.schemas_v1 import CompletePaymentedDealRequest


REAL_COMPLETE_PAYMENTED_DEAL_DATA = {
    "paygine_order_id": 13098239,
}


class CompletePaymentedDealIntegrationTest(unittest.IsolatedAsyncioTestCase):
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
