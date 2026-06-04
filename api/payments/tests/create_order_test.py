from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

from api.payments.payments_methods import register_deal
from api.schemas.schemas_v1 import RegisterDealPaymentRequest


REAL_REGISTER_DEAL_DATA = {
    "request": {
        "order_id": 101,
        "customer": {
            "client_ref": "test-customer-101",
            "email": "customer@example.com",
            "phone": "79000000001",
        },
        "performer": {
            "client_ref": "test-performer-101",
            "email": "performer@example.com",
            "phone": "79000000002",
        },
        "amount": 10000,
        "service_fee_amount": Decimal("500.00"),
        "customer_payment_amount": Decimal("10500.00"),
        "performer_payout_amount": Decimal("10000.00"),
        "expires_at": datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc),
        "description": "Оплата тестовой сделки",
        "currency": 643,
        "fee": 500,
        "mode": 1,
    },
    "reference_prefix": "real-paygine-register-deal",
}


class RegisterDealIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_register_deal_returns_real_paygine_order_id_without_db_save(self):
        """Отправляем реальный запрос в ПЦ и не сохраняем данные в нашу БД."""
        request_data = dict(REAL_REGISTER_DEAL_DATA["request"])
        request_data["reference"] = (
            f"{REAL_REGISTER_DEAL_DATA['reference_prefix']}-{uuid4().hex[:12]}"
        )
        payment_data = RegisterDealPaymentRequest(**request_data)
        saved_payment_calls = []

        async def skip_payment_data_save(
            data: RegisterDealPaymentRequest,
            paygine_order_id: str,
        ) -> None:
            saved_payment_calls.append(
                {
                    "order_id": data.order_id,
                    "paygine_order_id": paygine_order_id,
                }
            )

        with patch(
            "api.payments.utils.register_deal_methods.save_order_payment_data",
            new=skip_payment_data_save,
        ):
            response = await register_deal(payment_data)

        self.assertTrue(response["paygine_order_id"])
        self.assertEqual(response["customer_ref"], payment_data.customer.client_ref)
        self.assertEqual(response["performer_ref"], payment_data.performer.client_ref)
        self.assertIn(response["paygine_order_id"], response["raw_response"])
        self.assertEqual(
            saved_payment_calls,
            [
                {
                    "order_id": payment_data.order_id,
                    "paygine_order_id": response["paygine_order_id"],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
