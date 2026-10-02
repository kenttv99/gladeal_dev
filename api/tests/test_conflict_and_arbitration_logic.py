from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from api.config import EXPIRE_TIME_TO_COMNFIRM_MINUTES
from api.enums.enums_v1 import OrderPaymentStates, OrderStates
from api.exceptions import ValidationError
from api.utils import admins_methods
from api.utils.help_orders_method import (
    add_order_status_history,
    is_cancellation_within_hold_duration,
)
from workers.utils import order_expire_methods
from workers.utils.order_expire_methods import (
    EXPIRED_ORDER_ACTIONS,
    claim_expired_order_ids,
    expire_cancled_order,
    expire_confirmed_order,
    expire_conflict_cancelled_order,
    process_expired_orders,
)


class FakeResult:
    def __init__(self, row):
        self.row = row

    def one_or_none(self):
        return self.row

    def all(self):
        return self.row if isinstance(self.row, list) else [self.row]


class FakeSession:
    def __init__(self, execute_results=None, scalar_results=None):
        self.execute_results = list(execute_results or [])
        self.scalar_results = list(scalar_results or [])
        self.statements = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def begin(self):
        return self

    async def execute(self, statement):
        self.statements.append(statement)
        if self.execute_results:
            return self.execute_results.pop(0)
        return None

    async def scalar(self, statement):
        self.statements.append(statement)
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    async def scalars(self, statement):
        self.statements.append(statement)
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return FakeResult([])


class OrderExpirationTimingTest(unittest.TestCase):
    def test_three_days_cutoff_matches_config(self):
        # 4320 minutes = 72 hours = 3 days
        self.assertEqual(float(EXPIRE_TIME_TO_COMNFIRM_MINUTES), 4320.0)
        checked_at = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)
        cutoff = checked_at - timedelta(minutes=float(EXPIRE_TIME_TO_COMNFIRM_MINUTES))
        expected_cutoff = checked_at - timedelta(days=3)
        self.assertEqual(cutoff, expected_cutoff)

    def test_cutoff_comparison(self):
        checked_at = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)
        cutoff = checked_at - timedelta(minutes=float(EXPIRE_TIME_TO_COMNFIRM_MINUTES))

        # Event 2.9 days ago (less than 72 hours) -> NOT expired yet
        event_recent = checked_at - timedelta(days=2, hours=23)
        self.assertFalse(event_recent <= cutoff)

        # Event exactly 3 days ago (72 hours) -> expired
        event_exact = checked_at - timedelta(days=3)
        self.assertTrue(event_exact <= cutoff)

        # Event 3.5 days ago -> expired (day 4)
        event_day_four = checked_at - timedelta(days=3, hours=12)
        self.assertTrue(event_day_four <= cutoff)


class HoldAnchorDurationTest(unittest.TestCase):
    def test_hold_starts_from_performer_connected_at_when_connected_after_payment(self):
        payment_authorized_at = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        # Performer connected 20 minutes later
        performer_connected_at = datetime(2026, 10, 1, 12, 20, 0, tzinfo=timezone.utc)

        # Client cancels 3 minutes after performer connection (23 mins after payment) -> within hold!
        cancel_at = datetime(2026, 10, 1, 12, 23, 0, tzinfo=timezone.utc)
        self.assertTrue(
            is_cancellation_within_hold_duration(payment_authorized_at, cancel_at, performer_connected_at)
        )

        # Client cancels 6 minutes after performer connection -> outside hold
        cancel_late = datetime(2026, 10, 1, 12, 26, 0, tzinfo=timezone.utc)
        self.assertFalse(
            is_cancellation_within_hold_duration(payment_authorized_at, cancel_late, performer_connected_at)
        )

    def test_hold_starts_from_payment_when_performer_connected_before_payment(self):
        performer_connected_at = datetime(2026, 10, 1, 11, 50, 0, tzinfo=timezone.utc)
        payment_authorized_at = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Cancel 4 mins after payment -> within hold
        cancel_at = datetime(2026, 10, 1, 12, 4, 0, tzinfo=timezone.utc)
        self.assertTrue(
            is_cancellation_within_hold_duration(payment_authorized_at, cancel_at, performer_connected_at)
        )

        # Cancel 6 mins after payment -> outside hold
        cancel_late = datetime(2026, 10, 1, 12, 6, 0, tzinfo=timezone.utc)
        self.assertFalse(
            is_cancellation_within_hold_duration(payment_authorized_at, cancel_late, performer_connected_at)
        )


class AdminArbitrationDisputeTest(unittest.IsolatedAsyncioTestCase):
    async def test_close_order_to_client_requires_reason(self):
        with self.assertRaises(ValidationError):
            await admins_methods.close_order_to_client(1, 99, "")

        with self.assertRaises(ValidationError):
            await admins_methods.close_order_to_client(1, 99, "   ")

    async def test_close_order_to_performer_requires_reason(self):
        with self.assertRaises(ValidationError):
            await admins_methods.close_order_to_performer(1, 99, "")

        with self.assertRaises(ValidationError):
            await admins_methods.close_order_to_performer(1, 99, "   ")

    @patch("api.utils.admins_methods.complete_paymented_deal", new_callable=AsyncMock)
    @patch("api.utils.admins_methods.refund_money", new_callable=AsyncMock)
    @patch("api.utils.admins_methods.add_order_status_history", new_callable=AsyncMock)
    @patch("api.utils.admins_methods.AsyncSessionLocal")
    async def test_close_order_to_client_authorized_completes_payment_and_refunds(
        self,
        mock_session_local,
        mock_history,
        mock_refund,
        mock_complete,
    ):
        mock_refund.return_value = SimpleNamespace(
            payment_values=SimpleNamespace(
                paygine_payout_operation_id="refund_op_77",
            )
        )
        fake_row = (
            OrderStates.OPEN_CONFLICT.value,  # status
            10,  # client_id
            1000,  # price
            "Title",  # title
            OrderPaymentStates.AUTHORIZED.value,  # payment_status
            "client@example.com",  # customer_email
            None,  # paygine_revoked_operation_id
            None,  # revoke_status
            "+79991234567",  # phone_number
            "12345",  # paygine_payment_operation_id
        )
        fake_session = FakeSession(execute_results=[FakeResult(fake_row), None, None, None])
        mock_session_local.return_value = fake_session

        await admins_methods.close_order_to_client(1, 99, "Performer failed to deliver")

        # Must capture authorized payment before issuing refund (service fee retained in kubyshka)
        mock_complete.assert_awaited_once_with(12345)
        mock_refund.assert_awaited_once()
        mock_history.assert_awaited_once_with(
            fake_session,
            1,
            OrderStates.OPEN_CONFLICT.value,
            OrderStates.CLOSED_BY_ARBITER_TO_CLIENT.value,
            None,
            comment="Performer failed to deliver",
            changed_by_admin_id=99,
        )

    @patch("api.utils.admins_methods.complete_paymented_deal", new_callable=AsyncMock)
    @patch("api.utils.admins_methods.refund_money", new_callable=AsyncMock)
    @patch("api.utils.admins_methods.add_order_status_history", new_callable=AsyncMock)
    @patch("api.utils.admins_methods.AsyncSessionLocal")
    async def test_close_order_to_client_completed_performs_refund(
        self,
        mock_session_local,
        mock_history,
        mock_refund,
        mock_complete,
    ):
        mock_refund.return_value = SimpleNamespace(
            payment_values=SimpleNamespace(
                paygine_payout_operation_id="refund_op_77",
            )
        )
        fake_row = (
            OrderStates.OPEN_CONFLICT.value,  # status
            10,  # client_id
            1000,  # price
            "Title",  # title
            OrderPaymentStates.COMPLETED.value,  # payment_status
            "client@example.com",  # customer_email
            None,  # paygine_revoked_operation_id
            None,  # revoke_status
            "+79991234567",  # phone_number
            "12345",  # paygine_payment_operation_id
        )
        fake_session = FakeSession(execute_results=[FakeResult(fake_row), None, None])
        mock_session_local.return_value = fake_session

        await admins_methods.close_order_to_client(1, 99, "Work was incomplete")

        # Already completed, must not call complete_paymented_deal again
        mock_complete.assert_not_called()
        mock_refund.assert_awaited_once()
        mock_history.assert_awaited_once_with(
            fake_session,
            1,
            OrderStates.OPEN_CONFLICT.value,
            OrderStates.CLOSED_BY_ARBITER_TO_CLIENT.value,
            None,
            comment="Work was incomplete",
            changed_by_admin_id=99,
        )

    @patch("api.utils.admins_methods.complete_paymented_deal", new_callable=AsyncMock)
    @patch("api.utils.admins_methods.register_payout_deal", new_callable=AsyncMock)
    @patch("api.utils.admins_methods.add_order_status_history", new_callable=AsyncMock)
    @patch("api.utils.admins_methods.AsyncSessionLocal")
    async def test_close_order_to_performer_authorized_completes_payment_first(
        self,
        mock_session_local,
        mock_history,
        mock_payout,
        mock_complete,
    ):
        mock_payout.return_value = SimpleNamespace(
            payment_values=SimpleNamespace(
                paygine_payout_operation_id="payout_op_99",
                expire_payout_at=None,
            )
        )
        fake_row = (
            OrderStates.OPEN_CONFLICT.value,  # status
            20,  # performer_id
            1000,  # price
            "Title",  # title
            OrderPaymentStates.AUTHORIZED.value,  # payment_status
            "performer@example.com",  # performer_email
            None,  # paygine_payout_operation_id
            None,  # payout_status
            "+79997654321",  # performer_phone
            "12345",  # paygine_payment_operation_id
        )
        fake_session = FakeSession(execute_results=[FakeResult(fake_row), None, None, None])
        mock_session_local.return_value = fake_session

        await admins_methods.close_order_to_performer(1, 99, "Work delivered fully per spec")

        # Must capture authorized payment before issuing payout
        mock_complete.assert_awaited_once_with(12345)
        mock_payout.assert_awaited_once()
        mock_history.assert_awaited_once_with(
            fake_session,
            1,
            OrderStates.OPEN_CONFLICT.value,
            OrderStates.CLOSED_BY_ARBITER_TO_PERFORMER.value,
            None,
            comment="Work delivered fully per spec",
            changed_by_admin_id=99,
        )

    @patch("api.utils.admins_methods.complete_paymented_deal", new_callable=AsyncMock)
    @patch("api.utils.admins_methods.register_payout_deal", new_callable=AsyncMock)
    @patch("api.utils.admins_methods.add_order_status_history", new_callable=AsyncMock)
    @patch("api.utils.admins_methods.AsyncSessionLocal")
    async def test_close_order_to_performer_completed_registers_payout(
        self,
        mock_session_local,
        mock_history,
        mock_payout,
        mock_complete,
    ):
        mock_payout.return_value = SimpleNamespace(
            payment_values=SimpleNamespace(
                paygine_payout_operation_id="payout_op_99",
                expire_payout_at=None,
            )
        )
        fake_row = (
            OrderStates.OPEN_CONFLICT.value,  # status
            20,  # performer_id
            1000,  # price
            "Title",  # title
            OrderPaymentStates.COMPLETED.value,  # payment_status
            "performer@example.com",  # performer_email
            None,  # paygine_payout_operation_id
            None,  # payout_status
            "+79997654321",  # performer_phone
            "12345",  # paygine_payment_operation_id
        )
        fake_session = FakeSession(execute_results=[FakeResult(fake_row), None, None])
        mock_session_local.return_value = fake_session

        await admins_methods.close_order_to_performer(1, 99, "Work delivered fully per spec")

        # Payment already completed, complete_paymented_deal must NOT be called
        mock_complete.assert_not_called()
        mock_payout.assert_awaited_once()
        mock_history.assert_awaited_once_with(
            fake_session,
            1,
            OrderStates.OPEN_CONFLICT.value,
            OrderStates.CLOSED_BY_ARBITER_TO_PERFORMER.value,
            None,
            comment="Work delivered fully per spec",
            changed_by_admin_id=99,
        )


class WorkerConflictCancelExpirationTest(unittest.IsolatedAsyncioTestCase):
    def test_expired_order_actions_includes_conflict_cancel(self):
        self.assertIn("conflict_cancel", EXPIRED_ORDER_ACTIONS)

    @patch("workers.utils.order_expire_methods.reverse_paymented_deal", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.refund_money", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.get_expired_conflict_refund_data", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.add_order_status_history", new_callable=AsyncMock)
    async def test_expire_conflict_cancelled_order_authorized(
        self,
        mock_history,
        mock_get_refund_data,
        mock_refund_money,
        mock_reverse,
    ):
        mock_session = FakeSession(execute_results=[None, None])
        mock_get_refund_data.return_value = SimpleNamespace(
            current_status=OrderStates.AWAITING_CONFLICT.value,
            client_id=10,
            customer_email="client@example.com",
            customer_phone="+79991234567",
            price=1500,
            title="Design logo",
            paygine_payment_operation_id=123,
            payment_status=OrderPaymentStates.AUTHORIZED.value,
        )

        await expire_conflict_cancelled_order(mock_session, 1)

        # In AUTHORIZED state, worker reverses payment deal
        mock_reverse.assert_awaited_once_with(123)
        mock_refund_money.assert_not_called()
        mock_history.assert_awaited_once()

    @patch("workers.utils.order_expire_methods.reverse_paymented_deal", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.refund_money", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.get_expired_conflict_refund_data", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.set_expired_order_refund_status", new_callable=AsyncMock)
    async def test_expire_conflict_cancelled_order_completed(
        self,
        mock_set_status,
        mock_get_refund_data,
        mock_refund_money,
        mock_reverse,
    ):
        mock_session = FakeSession(execute_results=[None, None])
        mock_get_refund_data.return_value = SimpleNamespace(
            current_status=OrderStates.AWAITING_CONFLICT.value,
            client_id=10,
            customer_email="client@example.com",
            customer_phone="+79991234567",
            price=1500,
            title="Design logo",
            paygine_payment_operation_id=123,
            payment_status=OrderPaymentStates.COMPLETED.value,
        )
        mock_refund_money.return_value = SimpleNamespace(
            payment_values=SimpleNamespace(
                paygine_payout_operation_id="refund_op_88",
            )
        )

        await expire_conflict_cancelled_order(mock_session, 1)

        # In COMPLETED state, worker issues refund via Paygine
        mock_reverse.assert_not_called()
        mock_refund_money.assert_awaited_once()
        mock_set_status.assert_awaited_once_with(
            mock_session,
            1,
            OrderStates.AWAITING_CONFLICT.value,
            "refund_op_88",
            comment="Автоматическая отмена сделки по истечении 3 дней молчания исполнителя",
        )

    @patch("workers.utils.order_expire_methods.reverse_paymented_deal", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.refund_money", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.get_expired_payment_order_data", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.add_order_status_history", new_callable=AsyncMock)
    async def test_expire_cancled_order_authorized(
        self,
        mock_history,
        mock_get_refund_data,
        mock_refund_money,
        mock_reverse,
    ):
        mock_session = FakeSession(execute_results=[None, None])
        mock_get_refund_data.return_value = SimpleNamespace(
            current_status=OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
            client_id=10,
            customer_email="client@example.com",
            customer_phone="+79991234567",
            price=1500,
            title="Design logo",
            paygine_payment_operation_id=123,
            payment_status=OrderPaymentStates.AUTHORIZED.value,
        )

        await expire_cancled_order(mock_session, 1)

        mock_reverse.assert_awaited_once_with(123)
        mock_refund_money.assert_not_called()
        mock_history.assert_awaited_once()

    @patch("workers.utils.order_expire_methods.reverse_paymented_deal", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.refund_money", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.get_expired_payment_order_data", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.set_expired_order_refund_status", new_callable=AsyncMock)
    async def test_expire_cancled_order_completed(
        self,
        mock_set_status,
        mock_get_refund_data,
        mock_refund_money,
        mock_reverse,
    ):
        mock_session = FakeSession(execute_results=[None, None])
        mock_get_refund_data.return_value = SimpleNamespace(
            current_status=OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
            client_id=10,
            customer_email="client@example.com",
            customer_phone="+79991234567",
            price=1500,
            title="Design logo",
            paygine_payment_operation_id=123,
            payment_status=OrderPaymentStates.COMPLETED.value,
        )
        mock_refund_money.return_value = SimpleNamespace(
            payment_values=SimpleNamespace(
                paygine_payout_operation_id="refund_op_99",
            )
        )

        await expire_cancled_order(mock_session, 1)

        mock_reverse.assert_not_called()
        mock_refund_money.assert_awaited_once()
        mock_set_status.assert_awaited_once_with(
            mock_session,
            1,
            OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
            "refund_op_99",
            comment="Автоматическая отмена сделки по истечении времени подтверждения исполнителем",
        )

    @patch("workers.utils.order_expire_methods.complete_paymented_deal", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.register_payout_deal", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.get_expired_payout_order_data", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.set_expired_order_payout_status", new_callable=AsyncMock)
    async def test_expire_confirmed_order_authorized_captures_hold(
        self,
        mock_set_status,
        mock_get_payout_data,
        mock_register_payout,
        mock_complete_payment,
    ):
        mock_session = FakeSession(execute_results=[None])
        mock_get_payout_data.return_value = SimpleNamespace(
            current_status=OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
            paygine_payment_operation_id=123,
            performer_id=20,
            performer_email="performer@example.com",
            performer_phone="+79997654321",
            price=2000,
            title="Design logo",
            payment_status=OrderPaymentStates.AUTHORIZED.value,
        )
        mock_register_payout.return_value = SimpleNamespace(
            payment_values=SimpleNamespace(
                paygine_payout_operation_id="payout_op_77",
                expire_payout_at=None,
            )
        )

        await expire_confirmed_order(mock_session, 1)

        mock_complete_payment.assert_awaited_once_with(123)
        mock_register_payout.assert_awaited_once()
        mock_set_status.assert_awaited_once_with(
            mock_session,
            1,
            OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
            "payout_op_77",
            None,
        )

    @patch("workers.utils.order_expire_methods.complete_paymented_deal", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.register_payout_deal", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.get_expired_payout_order_data", new_callable=AsyncMock)
    @patch("workers.utils.order_expire_methods.set_expired_order_payout_status", new_callable=AsyncMock)
    async def test_expire_confirmed_order_completed_proceeds_directly(
        self,
        mock_set_status,
        mock_get_payout_data,
        mock_register_payout,
        mock_complete_payment,
    ):
        mock_session = FakeSession(execute_results=[None])
        mock_get_payout_data.return_value = SimpleNamespace(
            current_status=OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
            paygine_payment_operation_id=123,
            performer_id=20,
            performer_email="performer@example.com",
            performer_phone="+79997654321",
            price=2000,
            title="Design logo",
            payment_status=OrderPaymentStates.COMPLETED.value,
        )
        mock_register_payout.return_value = SimpleNamespace(
            payment_values=SimpleNamespace(
                paygine_payout_operation_id="payout_op_77",
                expire_payout_at=None,
            )
        )

        await expire_confirmed_order(mock_session, 1)

        mock_complete_payment.assert_not_called()
        mock_register_payout.assert_awaited_once()
        mock_set_status.assert_awaited_once()

    @patch("workers.utils.order_expire_methods.claim_expired_order_ids")
    @patch("workers.utils.order_expire_methods.expire_order", new_callable=AsyncMock)
    async def test_process_expired_orders_continues_on_exception(
        self,
        mock_expire_order,
        mock_claim,
    ):
        mock_claim.side_effect = [
            {"cancle": [1, 2], "confirm": [], "conflict_cancel": []},
            {"cancle": [], "confirm": [], "conflict_cancel": []},
        ]
        mock_expire_order.side_effect = [RuntimeError("Paygine gateway error"), None]

        fake_session = FakeSession()
        processed = await process_expired_orders(fake_session)

        self.assertEqual(processed["cancle"], 1)
        self.assertEqual(mock_expire_order.await_count, 2)

    async def test_claim_expired_order_ids_collects_batches(self):
        fake_session = FakeSession(
            scalar_results=[
                FakeResult([10, 11]),
                FakeResult([20]),
                FakeResult([30, 31, 32]),
            ]
        )
        result = await claim_expired_order_ids(fake_session, limit=50)

        self.assertEqual(result["cancle"], [10, 11])
        self.assertEqual(result["confirm"], [20])
        self.assertEqual(result["conflict_cancel"], [30, 31, 32])
        self.assertEqual(len(fake_session.statements), 3)


class AddOrderStatusHistoryAdminTest(unittest.IsolatedAsyncioTestCase):
    async def test_add_order_status_history_with_admin_id(self):
        fake_session = FakeSession()
        await add_order_status_history(
            session=fake_session,
            order_id=1,
            old_status=OrderStates.OPEN_CONFLICT,
            new_status=OrderStates.CLOSED_BY_ARBITER_TO_CLIENT.value,
            changed_by_user_id=None,
            comment="Resolved by arbiter",
            changed_by_admin_id=99,
        )
        self.assertEqual(len(fake_session.statements), 1)
        insert_stmt = fake_session.statements[0]
        params = insert_stmt.compile().params
        self.assertEqual(params["order_id"], 1)
        self.assertEqual(params["old_status"], "open_conflict")
        self.assertEqual(params["new_status"], "closed_by_arbiter_to_client")
        self.assertIsNone(params["changed_by_user_id"])
        self.assertEqual(params["changed_by_admin_id"], 99)
        self.assertEqual(params["comment"], "Resolved by arbiter")


class PerformerConflictOrderTest(unittest.IsolatedAsyncioTestCase):
    @patch("api.utils.orders_methods.complete_paymented_deal", new_callable=AsyncMock)
    @patch("api.utils.orders_methods.add_order_status_history", new_callable=AsyncMock)
    @patch("api.utils.orders_methods.ensure_user_exists", new_callable=AsyncMock)
    @patch("api.utils.orders_methods.AsyncSessionLocal")
    async def test_performer_conflict_authorized_completes_payment(
        self,
        mock_session_local,
        mock_ensure_user,
        mock_history,
        mock_complete,
    ):
        from api.utils import orders_methods

        fake_row = (
            OrderStates.AWAITING_CONFLICT.value,  # current_status
            10,  # client_id
            OrderPaymentStates.AUTHORIZED.value,  # payment_status
            "98765",  # payment_operation_id
        )
        fake_session = FakeSession(execute_results=[FakeResult(fake_row), None, None])
        mock_session_local.return_value = fake_session

        await orders_methods.performer_conflict_order(1, 20)

        mock_ensure_user.assert_awaited_once_with(fake_session, 20)
        mock_complete.assert_awaited_once_with(98765)
        mock_history.assert_awaited_once_with(
            fake_session,
            1,
            OrderStates.AWAITING_CONFLICT.value,
            OrderStates.OPEN_CONFLICT.value,
            20,
        )

    @patch("api.utils.orders_methods.complete_paymented_deal", new_callable=AsyncMock)
    @patch("api.utils.orders_methods.add_order_status_history", new_callable=AsyncMock)
    @patch("api.utils.orders_methods.ensure_user_exists", new_callable=AsyncMock)
    @patch("api.utils.orders_methods.AsyncSessionLocal")
    async def test_performer_conflict_completed_does_not_call_complete_again(
        self,
        mock_session_local,
        mock_ensure_user,
        mock_history,
        mock_complete,
    ):
        from api.utils import orders_methods

        fake_row = (
            OrderStates.AWAITING_CONFLICT.value,  # current_status
            10,  # client_id
            OrderPaymentStates.COMPLETED.value,  # payment_status
            "98765",  # payment_operation_id
        )
        fake_session = FakeSession(execute_results=[FakeResult(fake_row), None])
        mock_session_local.return_value = fake_session

        await orders_methods.performer_conflict_order(1, 20)

        mock_complete.assert_not_called()
        mock_history.assert_awaited_once()

    @patch("api.utils.orders_methods.complete_paymented_deal", new_callable=AsyncMock)
    @patch("api.utils.orders_methods.add_order_status_history", new_callable=AsyncMock)
    @patch("api.utils.orders_methods.ensure_user_exists", new_callable=AsyncMock)
    @patch("api.utils.orders_methods.AsyncSessionLocal")
    async def test_performer_conflict_authorized_missing_op_id_skips_complete(
        self,
        mock_session_local,
        mock_ensure_user,
        mock_history,
        mock_complete,
    ):
        from api.utils import orders_methods

        fake_row = (
            OrderStates.AWAITING_CONFLICT.value,
            10,
            OrderPaymentStates.AUTHORIZED.value,
            None,
        )
        fake_session = FakeSession(execute_results=[FakeResult(fake_row), None])
        mock_session_local.return_value = fake_session

        await orders_methods.performer_conflict_order(1, 20)

        mock_complete.assert_not_called()
        mock_history.assert_awaited_once()


