from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from api.exceptions import PaymentInvalidProviderResponseError
from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_BASE_URL, PAYGINE_SECTOR, SR_REF
from api.payments.payments_methods import register_payout_deal
from api.payments.utils.commission_methods import calculate_payment_amounts
from api.payments.utils.register_deal_methods import (
    build_payout_deal_payment_request,
    build_payout_order_payment_values,
    build_register_payout_deal_payload,
)
from api.schemas.schemas_v1 import (
    PayoutDealPaymentValues,
    RegisterPayoutDealPaymentRequest,
    RegisterPayoutDealPaymentResponse,
    RegisterPayoutDealProviderRequest,
)


REAL_REGISTER_PAYOUT_DEAL_DATA = {
    "request": {
        "order_id": 1066,
        "performer": {
            "client_ref": "test-performer-102",
            "email": "performer@example.com",
            "phone": "79000000002",
        },
        "amount": Decimal("10000.00"),
        "description": "Вывод средств по тестовой сделке",
        "notify_url": "https://gradually-civic-scorpion.cloudpub.ru/v1/paygine/webhook_order_status",
        "currency": 643,
    },
    "reference_prefix": "real-paygine-register-payout-deal",
}


class RegisterPayoutDealIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_build_payout_deal_payment_request_maps_order_data(self):
        """Собираем provider-контракт регистрации вывода из backend-данных."""
        payment_data = build_payout_deal_payment_request(
            RegisterPayoutDealPaymentRequest(
                order_id=1066,
                performer_id=102,
                performer_email="performer@example.com",
                performer_phone="79000000002",
                amount=Decimal("10000.00"),
                description="Вывод средств по тестовой сделке",
            )
        )

        self.assertEqual(payment_data.order_id, 1066)
        self.assertEqual(payment_data.performer.client_ref, "102")
        self.assertEqual(payment_data.performer.email, "performer@example.com")
        self.assertEqual(payment_data.performer.phone, "79000000002")
        self.assertEqual(payment_data.reference, "gladeal-order-1066-payout")

    async def test_build_payout_order_payment_values(self):
        """Достаем payout operation id из ответа регистрации ПЦ."""
        values = build_payout_order_payment_values(
            {"root_tag": "order", "data": {"id": "13130132"}}
        )

        self.assertEqual(values.paygine_payout_operation_id, "13130132")
        self.assertGreater(values.expire_payout_at, datetime.now(timezone.utc))

    async def test_register_payout_deal_payload_uses_performer_client_ref(self):
        """Собираем запрос регистрации вывода с client_ref исполнителя."""
        request_data = dict(REAL_REGISTER_PAYOUT_DEAL_DATA["request"])
        request_data["reference"] = (
            f"{REAL_REGISTER_PAYOUT_DEAL_DATA['reference_prefix']}-{uuid4().hex[:12]}"
        )
        payment_data = RegisterPayoutDealProviderRequest(**request_data)
        payload = build_register_payout_deal_payload(payment_data)
        payment_amounts = calculate_payment_amounts(payment_data.amount)
        expected_signature = build_signature(
            (PAYGINE_SECTOR, payment_amounts["order_amount"], payment_data.currency)
        )

        self.assertNotIn("payer_id", payload)
        self.assertNotIn("service_fee_amount", payload)
        self.assertEqual(payload["amount"], payment_amounts["order_amount"])
        self.assertEqual(payload["client_ref"], payment_data.performer.client_ref)
        self.assertEqual(payload["sd_ref"], SR_REF)
        self.assertEqual(payload["notify_url"], payment_data.notify_url)
        self.assertEqual(payload["url"], f"{PAYGINE_BASE_URL.rstrip('/')}/payment/success")
        self.assertEqual(payload["failurl"], f"{PAYGINE_BASE_URL.rstrip('/')}/payment/fail")
        self.assertEqual(payload["signature"], expected_signature)

    async def test_register_payout_deal_uses_payout_provider_request(self):
        """Регистрируем вывод через отдельный payout-flow."""
        payment_data = RegisterPayoutDealPaymentRequest(
            order_id=1066,
            performer_id=102,
            performer_email="performer@example.com",
            performer_phone="79000000002",
            amount=Decimal("10000.00"),
            description="Вывод средств по тестовой сделке",
        )
        payment_response = RegisterPayoutDealPaymentResponse(
            provider_response={"root_tag": "response", "data": {"id": "payout-operation"}},
            payment_values=PayoutDealPaymentValues(
                paygine_payout_operation_id="payout-operation",
                expire_payout_at=datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc),
            ),
        )

        with patch(
            "api.payments.payments_methods.create_payout_deal",
            new=AsyncMock(return_value=payment_response),
        ) as create_payout_deal:
            response = await register_payout_deal(payment_data)

        create_payout_deal.assert_awaited_once_with(payment_data)
        self.assertEqual(response, payment_response)

    async def test_register_payout_deal_returns_readable_paygine_response(self):
        """Отправляем реальный запрос регистрации вывода в ПЦ и получаем читаемый ответ."""
        payment_data = RegisterPayoutDealPaymentRequest(
            order_id=int(uuid4().int % 10_000_000_000),
            performer_id=102,
            performer_email="performer@example.com",
            performer_phone="79000000002",
            amount=Decimal("10000.00"),
            description="Вывод средств по тестовой сделке",
        )

        try:
            response = await register_payout_deal(payment_data)
        except PaymentInvalidProviderResponseError as exc:
            self.fail(f"Paygine payout register response parse error: {exc.details}")

        print(json.dumps(response.provider_response, ensure_ascii=False, indent=2))

        self.assertIn("root_tag", response.provider_response)
        self.assertIn("data", response.provider_response)
        self.assertIsInstance(response.payment_values.paygine_payout_operation_id, str)


if __name__ == "__main__":
    unittest.main()
