from __future__ import annotations

import unittest

from api.exceptions import OrderAlreadyAcceptedError
from api.utils.orders_methods import ensure_order_info_visible_to_user


class OrderInfoVisibilityTest(unittest.TestCase):
    def test_unassigned_order_is_visible_to_any_authorized_user(self):
        ensure_order_info_visible_to_user(client_id=1, performer_id=None, user_id=3)

    def test_assigned_order_is_visible_to_client(self):
        ensure_order_info_visible_to_user(client_id=1, performer_id=2, user_id=1)

    def test_assigned_order_is_visible_to_performer(self):
        ensure_order_info_visible_to_user(client_id=1, performer_id=2, user_id=2)

    def test_assigned_order_rejects_other_user(self):
        with self.assertRaises(OrderAlreadyAcceptedError):
            ensure_order_info_visible_to_user(client_id=1, performer_id=2, user_id=3)


if __name__ == "__main__":
    unittest.main()
