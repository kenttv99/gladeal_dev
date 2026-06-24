from __future__ import annotations

import unittest
from unittest.mock import patch

from api.exceptions import UserBannedError, UserNotFoundError
from api.utils import users_methods


class FakeSession:
    def __init__(self, scalar_result):
        self.scalar_result = scalar_result

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def scalar(self, statement):
        return self.scalar_result


class UserBanGuardTest(unittest.IsolatedAsyncioTestCase):
    async def test_allowed_user_passes(self):
        with patch.object(users_methods, "AsyncSessionLocal", return_value=FakeSession(False)):
            await users_methods.ensure_user_not_banned(1)

    async def test_banned_user_rejected(self):
        with patch.object(users_methods, "AsyncSessionLocal", return_value=FakeSession(True)):
            with self.assertRaises(UserBannedError):
                await users_methods.ensure_user_not_banned(1)

    async def test_missing_user_rejected(self):
        with patch.object(users_methods, "AsyncSessionLocal", return_value=FakeSession(None)):
            with self.assertRaises(UserNotFoundError):
                await users_methods.ensure_user_not_banned(1)


if __name__ == "__main__":
    unittest.main()
