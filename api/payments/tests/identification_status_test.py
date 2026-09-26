from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, patch

from api.exceptions import PaymentInvalidProviderResponseError
from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_SECTOR
from api.payments.payments_methods import check_identification_status
from api.payments.utils.identification_status_methods import (
    IDENTIFICATION_STATUS_SIGNATURE_FIELDS,
    build_identification_status_payload,
)


REAL_IDENTIFICATION_STATUS_DATA = {
    "first_name": "Иван",
    "patronymic": "Иванович",
    "last_name": "Иванов",
    "birth_date": "2000.09.12",
    "persondoc_number": "1234567890",
}


class IdentificationStatusIntegrationTest(unittest.IsolatedAsyncioTestCase):
    def test_build_identification_status_payload_fields_and_signature(self):
        first_name = REAL_IDENTIFICATION_STATUS_DATA["first_name"]
        patronymic = REAL_IDENTIFICATION_STATUS_DATA["patronymic"]
        last_name = REAL_IDENTIFICATION_STATUS_DATA["last_name"]
        birth_date = REAL_IDENTIFICATION_STATUS_DATA["birth_date"]
        persondoc_number = REAL_IDENTIFICATION_STATUS_DATA["persondoc_number"]

        payload = build_identification_status_payload(
            first_name=first_name,
            patronymic=patronymic,
            last_name=last_name,
            birth_date=birth_date,
            persondoc_number=persondoc_number,
        )

        expected_signature = build_signature((
            PAYGINE_SECTOR,
            first_name,
            patronymic,
            last_name,
            birth_date,
            persondoc_number,
        ))

        self.assertEqual(payload["mode"], 1)
        self.assertEqual(payload["sector"], PAYGINE_SECTOR)
        self.assertEqual(payload["first_name"], first_name)
        self.assertEqual(payload["patronymic"], patronymic)
        self.assertEqual(payload["last_name"], last_name)
        self.assertEqual(payload["birth_date"], birth_date)
        self.assertEqual(payload["persondoc_number"], persondoc_number)
        self.assertEqual(payload["signature"], expected_signature)

    def test_payload_truncates_long_strings(self):
        payload = build_identification_status_payload(
            first_name="A" * 50,
            patronymic="B" * 50,
            last_name="C" * 50,
            birth_date="2000.09.12_extra",
            persondoc_number="12345678901234567890_extra",
        )

        self.assertEqual(len(payload["first_name"]), 30)
        self.assertEqual(len(payload["patronymic"]), 30)
        self.assertEqual(len(payload["last_name"]), 30)
        self.assertEqual(len(payload["birth_date"]), 10)
        self.assertEqual(len(payload["persondoc_number"]), 20)

    async def test_identification_status_returns_readable_paygine_response(self):
        """Отправляем реальный запрос проверки KYC в ПЦ Paygine и получаем читаемый ответ."""
        try:
            response = await check_identification_status(
                first_name=REAL_IDENTIFICATION_STATUS_DATA["first_name"],
                patronymic=REAL_IDENTIFICATION_STATUS_DATA["patronymic"],
                last_name=REAL_IDENTIFICATION_STATUS_DATA["last_name"],
                birth_date=REAL_IDENTIFICATION_STATUS_DATA["birth_date"],
                persondoc_number=REAL_IDENTIFICATION_STATUS_DATA["persondoc_number"],
            )
        except PaymentInvalidProviderResponseError as exc:
            self.fail(f"Paygine identification response parse error: {exc.details}")

        print(json.dumps(response, ensure_ascii=False, indent=2))

        self.assertIn("root_tag", response)
        self.assertIn("data", response)
        self.assertIsInstance(response["root_tag"], str)

    async def test_check_identification_status_approved(self):
        fake_xml = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            "<response>"
            "<status>APPROVED</status>"
            "<persondoc_result>300</persondoc_result>"
            "<identification_level>40</identification_level>"
            "</response>"
        )

        with patch(
            "api.payments.utils.identification_status_methods.post_identification_status",
            new=AsyncMock(return_value=fake_xml),
        ):
            response = await check_identification_status(
                first_name="Иван",
                patronymic="Иванович",
                last_name="Иванов",
                birth_date="2000.09.12",
                persondoc_number="1234567890",
            )

        self.assertIn("data", response)
        self.assertEqual(response["data"]["status"], "APPROVED")
        self.assertEqual(response["data"]["persondoc_result"], "300")
        self.assertEqual(response["data"]["identification_level"], "40")

    async def test_check_identification_status_failure_with_reason(self):
        fake_xml = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            "<response>"
            "<status>FORMAT_ERROR</status>"
            "<persondoc_result>301</persondoc_result>"
            "<identification_level>0</identification_level>"
            "<persondoc_fail_reason>601</persondoc_fail_reason>"
            "</response>"
        )

        with patch(
            "api.payments.utils.identification_status_methods.post_identification_status",
            new=AsyncMock(return_value=fake_xml),
        ):
            response = await check_identification_status(
                first_name="Иван",
                patronymic="Иванович",
                last_name="Иванов",
                birth_date="2000.09.12",
                persondoc_number="1234567890",
            )

        self.assertEqual(response["data"]["status"], "FORMAT_ERROR")
        self.assertEqual(response["data"]["persondoc_result"], "301")
        self.assertEqual(response["data"]["identification_level"], "0")
        self.assertEqual(response["data"]["persondoc_fail_reason"], "601")


if __name__ == "__main__":
    unittest.main()
