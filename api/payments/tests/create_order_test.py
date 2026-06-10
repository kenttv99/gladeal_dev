from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from api.exceptions import PaymentInvalidProviderResponseError
from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_SECTOR, SR_REF
from api.payments.payments_methods import register_deposit_deal
from api.payments.utils.commission_methods import calculate_payment_amounts
from api.payments.utils.register_deal_methods import build_register_deal_payload
from api.schemas.schemas_v1 import RegisterDealPaymentRequest


REAL_REGISTER_DEAL_DATA = {
    "request": {
        "order_id": 102,
        "customer": {
            "client_ref": "test-customer-102",
            "email": "customer@example.com",
            "phone": "79000000001",
        },
        "amount": 1000000,
        "service_fee_amount": Decimal("850.00"),
        "expires_at": datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc),
        "description": "Оплата тестовой сделки",
        "currency": 643,
    },
    "reference_prefix": "real-paygine-register-deal",
}


class RegisterDealIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_register_deal_payload_contains_sd_ref(self):
        """Собираем запрос регистрации с обязательным sd_ref из .env.payments."""
        request_data = dict(REAL_REGISTER_DEAL_DATA["request"])
        request_data["reference"] = (
            f"{REAL_REGISTER_DEAL_DATA['reference_prefix']}-{uuid4().hex[:12]}"
        )
        payment_data = RegisterDealPaymentRequest(**request_data)
        payload = build_register_deal_payload(payment_data)
        payment_amounts = calculate_payment_amounts(payment_data.amount)
        expected_signature = build_signature(
            (
                PAYGINE_SECTOR,
                payment_amounts["total_amount_with_fee"],
                payment_data.currency,
            )
        )

        self.assertNotIn("fee", payload)
        self.assertEqual(payload["amount"], payment_amounts["total_amount_with_fee"])
        self.assertEqual(payload["sd_ref"], SR_REF)
        self.assertEqual(payload["signature"], expected_signature)

    async def test_calculate_payment_amounts_returns_payment_amounts(self):
        payment_amounts = calculate_payment_amounts(1000000)

        self.assertEqual(
            list(payment_amounts),
            ["total_amount_with_fee", "order_amount", "service_fee_amount"],
        )
        self.assertEqual(payment_amounts["total_amount_with_fee"], Decimal("1085000.00"))
        self.assertEqual(payment_amounts["order_amount"], Decimal("1000000.00"))
        self.assertEqual(payment_amounts["service_fee_amount"], Decimal("85000.00"))

    async def test_calculate_payment_amounts_truncates_fee_to_two_decimal_places(self):
        payment_amounts = calculate_payment_amounts(Decimal("1000006.81176470588235"))

        self.assertEqual(payment_amounts["service_fee_amount"], Decimal("85000.57"))
        self.assertEqual(payment_amounts["order_amount"], Decimal("1000006.81"))
        self.assertEqual(payment_amounts["total_amount_with_fee"], Decimal("1085007.38"))

    async def test_register_deal_returns_readable_paygine_response(self):
        """Отправляем реальный запрос в ПЦ и получаем читаемый ответ."""
        request_data = dict(REAL_REGISTER_DEAL_DATA["request"])
        request_data["reference"] = (
            f"{REAL_REGISTER_DEAL_DATA['reference_prefix']}-{uuid4().hex[:12]}"
        )
        payment_data = RegisterDealPaymentRequest(**request_data)

        try:
            response = await register_deposit_deal(payment_data)
        except PaymentInvalidProviderResponseError as exc:
            self.fail(f"Paygine register response parse error: {exc.details}")

        print(json.dumps(response, ensure_ascii=False, indent=2))

        self.assertIn("root_tag", response)
        self.assertIn("data", response)
        self.assertIsInstance(response["root_tag"], str)


if __name__ == "__main__":
    unittest.main()
