from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_SECTOR
from api.payments.payments_methods import reverse_paymented_deal
from api.payments.utils.reverse_paymented_deal_methods import (
    build_reverse_paymented_deal_payload,
    post_reverse_paymented_deal,
)


class ReversePaymentedDealTest(unittest.IsolatedAsyncioTestCase):
    async def test_reverse_paymented_deal_payload_uses_payment_operation_id(self):
        operation_id = 13130177
        payload = build_reverse_paymented_deal_payload(operation_id)
        expected_signature = build_signature(
            (PAYGINE_SECTOR, operation_id)
        )

        self.assertEqual(payload["id"], operation_id)
        self.assertEqual(payload["sector"], PAYGINE_SECTOR)
        self.assertEqual(payload["signature"], expected_signature)

    async def test_reverse_paymented_deal_calls_endpoint(self):
        operation_id = 13130177
        fake_xml = "<response><status>ok</status></response>"

        with patch("api.payments.utils.reverse_paymented_deal_methods.post_reverse_paymented_deal", new=AsyncMock(return_value=fake_xml)):
            response = await reverse_paymented_deal(operation_id)

        self.assertIn("root_tag", response)
        self.assertIn("data", response)


if __name__ == "__main__":
    unittest.main()
