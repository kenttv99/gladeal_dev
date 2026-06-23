from __future__ import annotations

import json
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from api.payments.payments_methods import refund_money
from api.payments.utils import refund_money_methods
from api.payments.utils.refund_money_methods import build_refund_money_payment_request
from api.schemas.schemas_v1 import RefundMoneyPaymentRequest


REAL_REFUND_MONEY_DATA = {
    "order_id": 1,
    "client_id": 102,
    "customer_email": "client@example.com",
    "customer_phone": "+79990000000",
    "amount": Decimal("10000"),
    "description": "Refund test",
}


class RefundMoneyIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_refund_money_request_uses_client_id(self):
        data = RefundMoneyPaymentRequest(**REAL_REFUND_MONEY_DATA)
        payment_data = build_refund_money_payment_request(data)

        self.assertEqual(payment_data.performer.client_ref, str(data.client_id))
        self.assertEqual(payment_data.amount, data.amount)
        self.assertEqual(payment_data.reference, f"gladeal-order-{data.order_id}-refund")

    async def test_refund_money_returns_readable_paygine_response(self):
        """Регистрируем возврат заказчику в ПЦ без сервисной комиссии."""
        data = RefundMoneyPaymentRequest(**REAL_REFUND_MONEY_DATA)

        with patch.object(
            refund_money_methods,
            "create_registered_payout_deal",
            new=AsyncMock(return_value={"data": {"id": "13130177"}}),
        ):
            response = await refund_money(data)

        print(json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2))

        self.assertIn("provider_response", response.model_dump())
        self.assertIsInstance(response.payment_values.paygine_payout_operation_id, str)


if __name__ == "__main__":
    unittest.main()
