from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from api.endpoints.v1 import users_endpoints
from api.enums.enums_v1 import UserRoles
from api.exceptions import UserNotFoundError
from api.schemas.schemas_v1 import UserInfoResponse
from api.servers.main import app
from api.utils.jwt_methods import authorize_user
from api.utils.users_methods import get_user_info
from database.models.users import KYCData, User


CREATED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
KYC_UPDATED_AT = datetime(2026, 1, 2, tzinfo=timezone.utc)


class FakeCountsResult:
    def __init__(self, counts: tuple[int, int, int]):
        self.counts = counts

    def one(self) -> tuple[int, int, int]:
        return self.counts


class FakeSession:
    def __init__(self, user=None, kyc_entry=None, counts=(0, 0, 0)):
        self.user = user
        self.kyc_entry = kyc_entry
        self.counts = counts

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def scalar(self, statement):
        table_str = str(statement)
        if "users" in table_str:
            return self.user
        if "kyc_data" in table_str:
            return self.kyc_entry
        return None

    async def execute(self, statement):
        return FakeCountsResult(self.counts)


def make_user() -> User:
    return User(
        id=42,
        first_name="Иван",
        patronymic="Иванович",
        last_name="Иванов",
        phone_number="+79991234567",
        birth_date=datetime(2000, 1, 15, tzinfo=timezone.utc),
        persondoc_number="1234 567890",
        ppd=True,
        month_sum_limit=Decimal("200000.00"),
        is_two_factor_enabled=True,
        two_factor_backup_codes=["hash-1", "hash-2"],
        is_banned=False,
        role=UserRoles.CLIENT,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


class UserInfoMethodTest(unittest.IsolatedAsyncioTestCase):
    async def test_returns_full_profile(self):
        user = make_user()
        kyc_entry = KYCData(
            user_id=user.id,
            kyc_status=True,
            kyc_level="20",
            created_at=CREATED_AT,
            updated_at=KYC_UPDATED_AT,
        )
        fake_session = FakeSession(user=user, kyc_entry=kyc_entry, counts=(3, 1, 2))
        with patch("api.utils.users_methods.AsyncSessionLocal", return_value=fake_session):
            info = await get_user_info(user.id)

        self.assertEqual(info.id, 42)
        self.assertEqual(info.role, UserRoles.CLIENT.value)
        self.assertEqual(info.first_name, "Иван")
        self.assertEqual(info.patronymic, "Иванович")
        self.assertEqual(info.last_name, "Иванов")
        self.assertEqual(info.phone_number, "+79991234567")
        self.assertEqual(info.birth_date, user.birth_date)
        self.assertEqual(info.persondoc_number, "1234 567890")
        self.assertTrue(info.ppd)
        self.assertEqual(info.month_sum_limit, Decimal("200000.00"))
        self.assertTrue(info.two_factor_enabled)
        self.assertEqual(info.backup_codes_remaining, 2)
        self.assertTrue(info.kyc_status)
        self.assertEqual(info.kyc_level, "20")
        self.assertEqual(info.kyc_updated_at, KYC_UPDATED_AT)
        self.assertFalse(info.is_banned)
        self.assertIsNone(info.ban_reason)
        self.assertIsNone(info.banned_at)
        self.assertEqual(info.created_at, CREATED_AT)
        self.assertEqual(info.updated_at, CREATED_AT)
        self.assertEqual(info.successful_orders_count, 3)
        self.assertEqual(info.unsuccessful_orders_count, 1)
        self.assertEqual(info.conflict_orders_count, 2)

    async def test_missing_kyc_entry_returns_defaults(self):
        user = make_user()
        fake_session = FakeSession(user=user, kyc_entry=None)
        with patch("api.utils.users_methods.AsyncSessionLocal", return_value=fake_session):
            info = await get_user_info(user.id)

        self.assertFalse(info.kyc_status)
        self.assertIsNone(info.kyc_level)
        self.assertIsNone(info.kyc_updated_at)

    async def test_missing_user_raises_not_found(self):
        fake_session = FakeSession(user=None)
        with patch("api.utils.users_methods.AsyncSessionLocal", return_value=fake_session):
            with self.assertRaises(UserNotFoundError):
                await get_user_info(999)


class UserInfoEndpointTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        app.dependency_overrides[authorize_user] = lambda: 42

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_route_is_mounted_under_auth(self):
        paths = {route.path for route in app.routes}
        self.assertIn("/api/v1/auth/info", paths)
        self.assertNotIn("/api/v1/users/info", paths)

    def test_requires_authorization(self):
        app.dependency_overrides.clear()
        response = TestClient(app).get("/api/v1/auth/info")
        self.assertEqual(response.status_code, 401)

    def test_returns_serialized_payload(self):
        payload = UserInfoResponse(
            id=42,
            role=UserRoles.CLIENT,
            last_name="Иванов",
            first_name="Иван",
            patronymic="Иванович",
            phone_number="+79991234567",
            birth_date=datetime(2000, 1, 15, tzinfo=timezone.utc),
            persondoc_number="1234 567890",
            ppd=True,
            month_sum_limit=Decimal("200000.00"),
            two_factor_enabled=False,
            backup_codes_remaining=0,
            kyc_status=True,
            kyc_level="20",
            kyc_updated_at=KYC_UPDATED_AT,
            is_banned=False,
            ban_reason=None,
            banned_at=None,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
            successful_orders_count=3,
            unsuccessful_orders_count=1,
            conflict_orders_count=0,
        )
        with patch.object(
            users_endpoints,
            "get_user_info_method",
            new=AsyncMock(return_value=payload),
        ):
            response = self.client.get("/api/v1/auth/info")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], 42)
        self.assertEqual(data["role"], "client")
        self.assertEqual(data["phone_number"], "+79991234567")
        self.assertEqual(data["first_name"], "Иван")
        self.assertEqual(Decimal(str(data["month_sum_limit"])), Decimal("200000.00"))
        self.assertEqual(data["backup_codes_remaining"], 0)
        self.assertEqual(data["kyc_level"], "20")
        self.assertEqual(data["successful_orders_count"], 3)
