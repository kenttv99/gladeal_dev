from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from api.endpoints.v1 import order_performer_endpoints


class PerformerBanGuardTest(unittest.IsolatedAsyncioTestCase):
    async def test_authorize_active_user_checks_ban(self):
        with patch.object(
            order_performer_endpoints,
            "ensure_user_not_banned",
            new=AsyncMock(),
        ) as ensure_not_banned:
            user_id = await order_performer_endpoints.authorize_active_user(10)

        ensure_not_banned.assert_awaited_once_with(10)
        self.assertEqual(user_id, 10)


if __name__ == "__main__":
    unittest.main()
