from __future__ import annotations

import json
import unittest

from api.exceptions import PaymentInvalidProviderResponseError
from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_SECTOR
from api.payments.payments_methods import refund_money
from api.payments.utils.refund_money_methods import build_refund_money_payload


REAL_REFUND_MONEY_DATA = {
    "paygine_payment_operation_id": 13130177,
}


class RefundMoneyIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_refund_money_payload_uses_payment_operation_id(self):
        operation_id = REAL_REFUND_MONEY_DATA["paygine_payment_operation_id"]
        payload = build_refund_money_payload(operation_id)
        expected_signature = build_signature(
            (PAYGINE_SECTOR, operation_id)
        )

        self.assertEqual(payload["id"], operation_id)
        self.assertEqual(payload["signature"], expected_signature)

    async def test_refund_money_returns_readable_paygine_response(self):
        """Возвращаем средства заказчику в ПЦ через SDReverse."""
        operation_id = REAL_REFUND_MONEY_DATA["paygine_payment_operation_id"]

        try:
            response = await refund_money(operation_id)
        except PaymentInvalidProviderResponseError as exc:
            self.fail(f"Paygine refund response parse error: {exc.details}")

        print(json.dumps(response, ensure_ascii=False, indent=2))

        self.assertIn("root_tag", response)
        self.assertIn("data", response)
        self.assertIsInstance(response["root_tag"], str)


if __name__ == "__main__":
    unittest.main()
