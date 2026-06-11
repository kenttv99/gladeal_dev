from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from api.exceptions import PaymentInvalidProviderResponseError, ValidationError
from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_SECTOR, SR_REF
from api.payments.payments_methods import register_deposit_deal
from api.payments.utils.commission_methods import calculate_payment_amounts
from api.payments.utils.deposit_deal_methods import (
    build_deposit_deal_payment_request,
    build_deposit_order_payment_values,
)
from api.payments.utils.register_deal_methods import (
    build_register_deal_payload,
)
from api.schemas.schemas_v1 import RegisterDealPaymentRequest


REAL_REGISTER_DEAL_DATA = {
    "request": {
        "order_id": 102,
        "customer": {
            "client_ref": "test-customer-102",
            "email": "customer@example.com",
            "phone": "79000000001",
        },
        "amount": Decimal("10000.00"),
        "expires_at": datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc),
        "description": "Оплата тестовой сделки",
        "notify_url": "https://gradually-civic-scorpion.cloudpub.ru/v1/paygine/webhook_order_status",
        "currency": 643,
    },
    "reference_prefix": "real-paygine-register-deal",
}


class RegisterDealIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_build_deposit_deal_payment_request_maps_order_data(self):
        payment_data = build_deposit_deal_payment_request(
            order_id=102,
            client_id=9,
            customer_email="customer@example.com",
            customer_phone="+7 (900) 000-00-01",
            amount=Decimal("10000.00"),
            expires_at=datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc),
            description="Оплата тестовой сделки",
        )

        self.assertEqual(payment_data.order_id, 102)
        self.assertEqual(payment_data.customer.client_ref, "9")
        self.assertEqual(payment_data.customer.phone, "79000000001")
        self.assertEqual(payment_data.reference, "gladeal-order-102")
        self.assertTrue(payment_data.notify_url.endswith("/v1/paygine/webhook_order_status"))

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
        self.assertEqual(payload["notify_url"], payment_data.notify_url)
        self.assertEqual(payload["signature"], expected_signature)

    async def test_register_deal_payload_normalizes_phone(self):
        request_data = dict(REAL_REGISTER_DEAL_DATA["request"])
        request_data["customer"] = {
            **request_data["customer"],
            "phone": "8 (900) 000-00-01",
        }
        request_data["reference"] = "test-register-phone"
        payment_data = RegisterDealPaymentRequest(**request_data)

        payload = build_register_deal_payload(payment_data)

        self.assertEqual(payload["phone"], "79000000001")

    async def test_register_deal_payload_rejects_invalid_phone(self):
        request_data = dict(REAL_REGISTER_DEAL_DATA["request"])
        request_data["customer"] = {
            **request_data["customer"],
            "phone": "string",
        }
        request_data["reference"] = "test-register-invalid-phone"
        payment_data = RegisterDealPaymentRequest(**request_data)

        with self.assertRaises(ValidationError):
            build_register_deal_payload(payment_data)

    async def test_build_deposit_order_payment_values(self):
        payment_data = RegisterDealPaymentRequest(
            **{
                **REAL_REGISTER_DEAL_DATA["request"],
                "reference": "test-register-values",
            }
        )
        values = build_deposit_order_payment_values(
            payment_data,
            {"data": {"id": "13130177"}},
        )

        self.assertEqual(values["currency"], 643)
        self.assertEqual(values["order_amount"], Decimal("10000"))
        self.assertEqual(values["service_fee_amount"], Decimal("850"))
        self.assertEqual(values["paygine_payment_operation_id"], "13130177")
        self.assertEqual(values["expires_at"], payment_data.expires_at)

    async def test_register_deal_returns_readable_paygine_response(self):
        """Отправляем реальный запрос в ПЦ и получаем читаемый ответ."""
        request_data = dict(REAL_REGISTER_DEAL_DATA["request"])
        request_data["reference"] = (
            f"{REAL_REGISTER_DEAL_DATA['reference_prefix']}-{uuid4().hex[:12]}"
        )
        payment_data = RegisterDealPaymentRequest(**request_data)

        try:
            result = await register_deposit_deal(
                order_id=payment_data.order_id,
                client_id=int(payment_data.customer.client_ref.rsplit("-", 1)[-1]),
                customer_email=payment_data.customer.email,
                customer_phone=payment_data.customer.phone or "",
                amount=payment_data.amount,
                expires_at=payment_data.expires_at,
                description=payment_data.description,
                currency=payment_data.currency,
            )
        except PaymentInvalidProviderResponseError as exc:
            self.fail(f"Paygine register response parse error: {exc.details}")

        print(json.dumps(result.provider_response, ensure_ascii=False, indent=2))

        self.assertIn("root_tag", result.provider_response)
        self.assertIn("data", result.provider_response)
        self.assertIsInstance(result.provider_response["root_tag"], str)


if __name__ == "__main__":
    unittest.main()
