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
        "service_fee_amount": Decimal("500.00"),
        "expires_at": datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc),
        "description": "Оплата тестовой сделки",
        "currency": 643,
        "fee": 50000,
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
        expected_signature = build_signature(
            (PAYGINE_SECTOR, payment_data.amount, payment_data.currency)
        )

        self.assertEqual(payload["sd_ref"], SR_REF)
        self.assertEqual(payload["signature"], expected_signature)

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
