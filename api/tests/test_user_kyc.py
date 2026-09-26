from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import AsyncMock, patch

from api.exceptions import UserNotFoundError, UserPersondocRequiredError
from api.schemas.schemas_v1 import UserKYCResponse
from api.utils.users_methods import get_user_kyc_data, verify_user_kyc
from database.models.users import KYCData, User


class FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    def __init__(self, user=None, kyc_entry=None):
        self.user = user
        self.kyc_entry = kyc_entry
        self.added = []
        self.flushed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def begin(self):
        return self

    async def scalar(self, statement):
        table_str = str(statement)
        if "users" in table_str:
            return self.user
        if "kyc_data" in table_str:
            return self.kyc_entry
        return None

    def add(self, entity):
        self.added.append(entity)
        if isinstance(entity, KYCData):
            self.kyc_entry = entity

    async def flush(self):
        self.flushed = True


class UserKYCTest(unittest.IsolatedAsyncioTestCase):
    async def test_verify_user_kyc_user_not_found(self):
        fake_session = FakeSession(user=None)
        with patch("api.utils.users_methods.AsyncSessionLocal", return_value=fake_session):
            with self.assertRaises(UserNotFoundError):
                await verify_user_kyc(user_id=999)

    async def test_verify_user_kyc_missing_persondoc_raises_error(self):
        user = User(
            id=1,
            first_name="Иван",
            patronymic="Иванович",
            last_name="Иванов",
            birth_date=datetime(2000, 9, 12, tzinfo=timezone.utc),
            persondoc_number=None,
        )
        fake_session = FakeSession(user=user)
        with patch("api.utils.users_methods.AsyncSessionLocal", return_value=fake_session):
            with self.assertRaises(UserPersondocRequiredError):
                await verify_user_kyc(user_id=1)

    async def test_verify_user_kyc_missing_birth_date_raises_error(self):
        user = User(
            id=1,
            first_name="Иван",
            patronymic="Иванович",
            last_name="Иванов",
            birth_date=None,
            persondoc_number="1234567890",
        )
        fake_session = FakeSession(user=user)
        with patch("api.utils.users_methods.AsyncSessionLocal", return_value=fake_session):
            with self.assertRaises(UserPersondocRequiredError):
                await verify_user_kyc(user_id=1)

    async def test_verify_user_kyc_approved_creates_kyc_data(self):
        user = User(
            id=1,
            first_name="Иван",
            patronymic="Иванович",
            last_name="Иванов",
            birth_date=datetime(2000, 9, 12, tzinfo=timezone.utc),
            persondoc_number="1234 567890",
        )
        fake_session = FakeSession(user=user, kyc_entry=None)
        mock_kyc_response = {
            "root_tag": "response",
            "data": {
                "status": "APPROVED",
                "persondoc_result": "300",
                "identification_level": "40",
            },
        }

        with (
            patch("api.utils.users_methods.AsyncSessionLocal", return_value=fake_session),
            patch(
                "api.utils.users_methods.check_identification_status",
                new=AsyncMock(return_value=mock_kyc_response),
            ) as mock_check,
        ):
            res = await verify_user_kyc(user_id=1)

        mock_check.assert_awaited_once_with(
            first_name="Иван",
            patronymic="Иванович",
            last_name="Иванов",
            birth_date="2000.09.12",
            persondoc_number="1234 567890",
        )
        self.assertTrue(res.kyc_status)
        self.assertEqual(res.kyc_level, "40")
        self.assertEqual(res.provider_status, "APPROVED")
        self.assertEqual(res.identification_level, "40")
        self.assertEqual(res.persondoc_result, "300")
        self.assertIsNotNone(fake_session.kyc_entry)
        self.assertTrue(fake_session.kyc_entry.kyc_status)
        self.assertEqual(fake_session.kyc_entry.kyc_level, "40")

    async def test_verify_user_kyc_failure_updates_existing_kyc_data(self):
        user = User(
            id=1,
            first_name="Иван",
            patronymic="Иванович",
            last_name="Иванов",
            birth_date=datetime(2000, 9, 12, tzinfo=timezone.utc),
            persondoc_number="1234 567890",
        )
        existing_kyc = KYCData(
            id=5,
            user_id=1,
            kyc_level="40",
            kyc_status=True,
        )
        fake_session = FakeSession(user=user, kyc_entry=existing_kyc)
        mock_kyc_response = {
            "root_tag": "response",
            "data": {
                "status": "FORMAT_ERROR",
                "persondoc_result": "301",
                "identification_level": "0",
                "persondoc_fail_reason": "601",
            },
        }

        with (
            patch("api.utils.users_methods.AsyncSessionLocal", return_value=fake_session),
            patch(
                "api.utils.users_methods.check_identification_status",
                new=AsyncMock(return_value=mock_kyc_response),
            ),
        ):
            res = await verify_user_kyc(user_id=1)

        self.assertFalse(res.kyc_status)
        self.assertEqual(res.kyc_level, "0")
        self.assertEqual(res.persondoc_fail_reason, "601")
        self.assertFalse(existing_kyc.kyc_status)
        self.assertEqual(existing_kyc.kyc_level, "0")

    async def test_get_user_kyc_data_returns_status(self):
        user = User(id=1, first_name="Иван", last_name="Иванов")
        kyc = KYCData(id=1, user_id=1, kyc_level="40", kyc_status=True)
        fake_session = FakeSession(user=user, kyc_entry=kyc)

        with patch("api.utils.users_methods.AsyncSessionLocal", return_value=fake_session):
            res = await get_user_kyc_data(user_id=1)

        self.assertEqual(res.user_id, 1)
        self.assertTrue(res.kyc_status)
        self.assertEqual(res.kyc_level, "40")


if __name__ == "__main__":
    unittest.main()
