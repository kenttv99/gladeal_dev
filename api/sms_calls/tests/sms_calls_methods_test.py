import unittest

from api.sms_calls.config import PROSTO_SMS_API_KEY
from api.sms_calls.utils.calls_methods import build_prosto_call_payload
from api.sms_calls.utils.code_generator import generate_verification_code
from api.sms_calls.utils.sms_methods import build_prosto_sms_payload


class SmsCallsMethodsTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
