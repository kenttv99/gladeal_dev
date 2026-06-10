from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from api.exceptions import PaymentInvalidProviderResponseError
from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_SECTOR, SR_REF
from api.payments.payments_methods import register_payout_deal
from api.payments.utils.register_deal_methods import build_register_payout_deal_payload
from api.schemas.schemas_v1 import RegisterPayoutDealPaymentRequest


REAL_REGISTER_PAYOUT_DEAL_DATA = {
    "request": {
        "order_id": 1066,
        "performer": {
            "client_ref": "test-performer-102",
            "email": "performer@example.com",
            "phone": "79000000002",
        },
        "amount": 950000,
        "expires_at": datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc),
        "description": "Вывод средств по тестовой сделке",
        "currency": 643,
    },
    "reference_prefix": "real-paygine-register-payout-deal",
}


class RegisterPayoutDealIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_register_payout_deal_payload_uses_performer_client_ref(self):
        """Собираем запрос регистрации вывода с client_ref исполнителя."""
        request_data = dict(REAL_REGISTER_PAYOUT_DEAL_DATA["request"])
        request_data["reference"] = (
            f"{REAL_REGISTER_PAYOUT_DEAL_DATA['reference_prefix']}-{uuid4().hex[:12]}"
        )
        payment_data = RegisterPayoutDealPaymentRequest(**request_data)
        payload = build_register_payout_deal_payload(payment_data)
        expected_signature = build_signature(
            (PAYGINE_SECTOR, payment_data.amount, payment_data.currency)
        )

        self.assertNotIn("payer_id", payload)
        self.assertNotIn("service_fee_amount", payload)
        self.assertEqual(payload["client_ref"], payment_data.performer.client_ref)
        self.assertEqual(payload["sd_ref"], SR_REF)
        self.assertEqual(payload["signature"], expected_signature)

    async def test_register_payout_deal_uses_payout_provider_request(self):
        """Регистрируем вывод через отдельный payout-flow."""
        request_data = dict(REAL_REGISTER_PAYOUT_DEAL_DATA["request"])
        request_data["reference"] = (
            f"{REAL_REGISTER_PAYOUT_DEAL_DATA['reference_prefix']}-{uuid4().hex[:12]}"
        )
        payment_data = RegisterPayoutDealPaymentRequest(**request_data)
        provider_response = {"root_tag": "response", "data": {"id": "payout-operation"}}

        with patch(
            "api.payments.payments_methods.create_registered_payout_deal",
            new=AsyncMock(return_value=provider_response),
        ) as create_registered_payout_deal:
            response = await register_payout_deal(payment_data)

        create_registered_payout_deal.assert_awaited_once_with(payment_data)
        self.assertEqual(response, provider_response)

    async def test_register_payout_deal_returns_readable_paygine_response(self):
        """Отправляем реальный запрос регистрации вывода в ПЦ и получаем читаемый ответ."""
        request_data = dict(REAL_REGISTER_PAYOUT_DEAL_DATA["request"])
        request_data["reference"] = (
            f"{REAL_REGISTER_PAYOUT_DEAL_DATA['reference_prefix']}-{uuid4().hex[:12]}"
        )
        payment_data = RegisterPayoutDealPaymentRequest(**request_data)

        try:
            response = await register_payout_deal(payment_data)
        except PaymentInvalidProviderResponseError as exc:
            self.fail(f"Paygine payout register response parse error: {exc.details}")

        print(json.dumps(response, ensure_ascii=False, indent=2))

        self.assertIn("root_tag", response)
        self.assertIn("data", response)
        self.assertIsInstance(response["root_tag"], str)


if __name__ == "__main__":
    unittest.main()
