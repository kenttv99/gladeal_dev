import unittest
from os import environ
from unittest.mock import AsyncMock, patch

environ.setdefault("SMS_CALLS_REDIS_URL", "redis://localhost:6379/0")
environ.setdefault("SMS_CALLS_CODE_TTL_SECONDS", "300")

from api.sms_calls.config import PROSTO_SMS_API_KEY
from api.sms_calls.sms_calls_methods import send_user_sms_code
from api.sms_calls.utils.calls_methods import build_prosto_call_payload
from api.sms_calls.utils.code_generator import generate_verification_code
from api.sms_calls.utils.phone_methods import normalize_phone_to_int
from api.sms_calls.utils.sms_methods import build_prosto_sms_payload
from api.sms_calls.utils.verification_code_storage_methods import (
    build_user_verification_code_key,
)


class SmsCallsMethodsTest(unittest.IsolatedAsyncioTestCase):
    def test_generate_verification_code_returns_four_digits(self):
        code = generate_verification_code()

        self.assertEqual(len(code), 4)
        self.assertTrue(code.isdigit())

    def test_build_prosto_sms_payload(self):
        payload = build_prosto_sms_payload(79000000001, "1234")

        self.assertEqual(
            payload,
            {
                "method": "push_msg",
                "format": "json",
                "key": PROSTO_SMS_API_KEY,
                "text": "Код подтверждения: 1234",
                "phone": 79000000001,
                "sender_name": "Gladeal",
                "priority": 1,
            },
        )

    def test_build_prosto_call_payload(self):
        payload = build_prosto_call_payload(79000000001, "1234")

        self.assertEqual(payload["route"], "pc")
        self.assertEqual(payload["method"], "push_msg")
        self.assertEqual(payload["text"], "Код подтверждения: 1234")

    def test_build_user_verification_code_key(self):
        self.assertEqual(
            build_user_verification_code_key(15),
            "sms_calls:verification_code:user:15",
        )

    def test_normalize_phone_to_int(self):
        self.assertEqual(normalize_phone_to_int("+7 (900) 000-00-01"), 79000000001)

    async def test_send_user_sms_code_stores_code_and_hides_it_from_response(self):
        with (
            patch(
                "api.sms_calls.sms_calls_methods.generate_verification_code",
                return_value="1234",
            ),
            patch(
                "api.sms_calls.sms_calls_methods.save_user_verification_code",
                new=AsyncMock(),
            ) as save_code,
            patch(
                "api.sms_calls.sms_calls_methods.send_prosto_sms_code",
                new=AsyncMock(return_value={"response": "ok"}),
            ) as send_code,
        ):
            response = await send_user_sms_code(10, "+7 (900) 000-00-01")

        save_code.assert_awaited_once_with(10, "1234")
        send_code.assert_awaited_once_with(79000000001, "1234")
        self.assertEqual(response, {"success": True, "provider_response": {"response": "ok"}})
        self.assertNotIn("code", response)


if __name__ == "__main__":
    unittest.main()
