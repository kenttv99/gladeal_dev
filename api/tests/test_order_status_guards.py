from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from api.enums.enums_v1 import OrderPaymentStates, OrderStates
from api.exceptions import ValidationError
from api.utils import orders_methods
from api.utils.help_orders_method import (
    get_performer_decline_refund_data,
    set_client_refund_order_status,
    set_performer_declined_order_status,
    set_softdeclined_order_status,
)
from api.utils.order_status_webhook_methods import (
    WebhookOrderOperation,
    set_webhook_refund_completed,
)


class FakeResult:
    def __init__(self, row):
        self.row = row

    def one_or_none(self):
        return self.row


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
        return self.scalar_results.pop(0)


def compiled_params(statement):
    return statement.compile().params


class OrderStatusGuardServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_client_softdecline_from_awaiting_performer(self):
        session = FakeSession()
        with (
            patch.object(orders_methods, "AsyncSessionLocal", return_value=session),
            patch.object(
                orders_methods,
                "get_softdecline_payment_operation_id",
                new=AsyncMock(return_value=(10, OrderStates.AWAITING_PERFORMER.value)),
            ),
            patch.object(orders_methods, "cancle_unpayment_deal", new=AsyncMock()) as cancel,
            patch.object(
                orders_methods,
                "set_softdeclined_order_status",
                new=AsyncMock(),
            ) as set_status,
        ):
            await orders_methods.client_softdecline_order(1, 2)

        cancel.assert_awaited_once_with(10)
        set_status.assert_awaited_once_with(session, 1, OrderStates.AWAITING_PERFORMER.value, 2)

    async def test_client_softdecline_from_awaiting_payment(self):
        session = FakeSession()
        with (
            patch.object(orders_methods, "AsyncSessionLocal", return_value=session),
            patch.object(
                orders_methods,
                "get_softdecline_payment_operation_id",
                new=AsyncMock(return_value=(10, OrderStates.AWAITING_PAYMENT.value)),
            ),
            patch.object(orders_methods, "cancle_unpayment_deal", new=AsyncMock()) as cancel,
            patch.object(
                orders_methods,
                "set_softdeclined_order_status",
                new=AsyncMock(),
            ) as set_status,
        ):
            await orders_methods.client_softdecline_order(1, 2)

        cancel.assert_awaited_once_with(10)
        set_status.assert_awaited_once_with(session, 1, OrderStates.AWAITING_PAYMENT.value, 2)

    async def test_client_softdecline_from_paid_status_registers_refund(self):
        session = FakeSession()
        with (
            patch.object(orders_methods, "AsyncSessionLocal", return_value=session),
            patch.object(
                orders_methods,
                "get_softdecline_payment_operation_id",
                new=AsyncMock(side_effect=ValidationError()),
            ),
            patch.object(
                orders_methods,
                "get_client_softdecline_refund_data",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        current_status=OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
                        client_id=2,
                        customer_email="client@example.com",
                        customer_phone="+79990000000",
                        price=100,
                        title="Order",
                    )
                ),
            ),
            patch.object(orders_methods, "cancle_unpayment_deal", new=AsyncMock()) as cancel,
            patch.object(
                orders_methods,
                "refund_money",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        payment_values=SimpleNamespace(paygine_payout_operation_id="20")
                    )
                ),
            ) as refund,
            patch.object(
                orders_methods,
                "set_client_refund_order_status",
                new=AsyncMock(),
            ) as set_status,
        ):
            await orders_methods.client_softdecline_order(1, 2)

        cancel.assert_not_awaited()
        refund.assert_awaited_once()
        set_status.assert_awaited_once_with(
            session,
            1,
            OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
            2,
            "20",
        )

    async def test_client_softdecline_from_awaiting_client_payout_is_noop(self):
        session = FakeSession()
        with (
            patch.object(orders_methods, "AsyncSessionLocal", return_value=session),
            patch.object(
                orders_methods,
                "get_softdecline_payment_operation_id",
                new=AsyncMock(side_effect=ValidationError()),
            ),
            patch.object(
                orders_methods,
                "get_client_softdecline_refund_data",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        current_status=OrderStates.AWAITING_CLIENT_PAYOUT.value,
                    )
                ),
            ),
            patch.object(orders_methods, "refund_money", new=AsyncMock()) as refund,
            patch.object(
                orders_methods,
                "set_client_refund_order_status",
                new=AsyncMock(),
            ) as set_status,
        ):
            await orders_methods.client_softdecline_order(1, 2)

        refund.assert_not_awaited()
        set_status.assert_not_awaited()

    async def test_performer_decline_from_awaiting_payment(self):
        session = FakeSession()
        with (
            patch.object(orders_methods, "AsyncSessionLocal", return_value=session),
            patch.object(
                orders_methods,
                "get_performer_decline_refund_data",
                new=AsyncMock(
                    return_value=(
                        10,
                        SimpleNamespace(current_status=OrderStates.AWAITING_PAYMENT.value),
                    )
                ),
            ),
            patch.object(orders_methods, "cancle_unpayment_deal", new=AsyncMock()) as cancel,
            patch.object(orders_methods, "refund_money", new=AsyncMock()) as refund,
            patch.object(
                orders_methods,
                "set_softdeclined_order_status",
                new=AsyncMock(),
            ) as set_status,
        ):
            await orders_methods.performer_decline_order(1, 3)

        cancel.assert_awaited_once_with(10)
        refund.assert_not_awaited()
        set_status.assert_awaited_once_with(session, 1, OrderStates.AWAITING_PAYMENT.value, 3)

    async def test_performer_decline_from_awaiting_conflict(self):
        session = FakeSession()
        with (
            patch.object(orders_methods, "AsyncSessionLocal", return_value=session),
            patch.object(
                orders_methods,
                "get_performer_decline_refund_data",
                new=AsyncMock(
                    return_value=(
                        None,
                        SimpleNamespace(
                            current_status=OrderStates.AWAITING_CONFLICT.value,
                            client_id=2,
                            customer_email="client@example.com",
                            customer_phone="+79990000000",
                            price=100,
                            title="Order",
                        ),
                    )
                ),
            ),
            patch.object(orders_methods, "cancle_unpayment_deal", new=AsyncMock()) as cancel,
            patch.object(
                orders_methods,
                "refund_money",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        payment_values=SimpleNamespace(paygine_payout_operation_id="20")
                    )
                ),
            ) as refund,
            patch.object(
                orders_methods,
                "set_performer_declined_order_status",
                new=AsyncMock(),
            ) as set_status,
        ):
            await orders_methods.performer_decline_order(1, 3)

        cancel.assert_not_awaited()
        refund.assert_awaited_once()
        set_status.assert_awaited_once_with(
            session,
            1,
            OrderStates.AWAITING_CONFLICT.value,
            3,
            "20",
        )

    async def test_performer_decline_from_active_paid_status(self):
        session = FakeSession()
        with (
            patch.object(orders_methods, "AsyncSessionLocal", return_value=session),
            patch.object(
                orders_methods,
                "get_performer_decline_refund_data",
                new=AsyncMock(
                    return_value=(
                        None,
                        SimpleNamespace(
                            current_status=OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
                            client_id=2,
                            customer_email="client@example.com",
                            customer_phone="+79990000000",
                            price=100,
                            title="Order",
                        ),
                    )
                ),
            ),
            patch.object(orders_methods, "cancle_unpayment_deal", new=AsyncMock()) as cancel,
            patch.object(
                orders_methods,
                "refund_money",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        payment_values=SimpleNamespace(paygine_payout_operation_id="20")
                    )
                ),
            ) as refund,
            patch.object(
                orders_methods,
                "set_performer_declined_order_status",
                new=AsyncMock(),
            ) as set_status,
        ):
            await orders_methods.performer_decline_order(1, 3)

        cancel.assert_not_awaited()
        refund.assert_awaited_once()
        set_status.assert_awaited_once_with(
            session,
            1,
            OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
            3,
            "20",
        )

    async def test_performer_decline_from_awaiting_client_payout_is_noop(self):
        session = FakeSession()
        with (
            patch.object(orders_methods, "AsyncSessionLocal", return_value=session),
            patch.object(
                orders_methods,
                "get_performer_decline_refund_data",
                new=AsyncMock(
                    return_value=(
                        None,
                        SimpleNamespace(current_status=OrderStates.AWAITING_CLIENT_PAYOUT.value),
                    )
                ),
            ),
            patch.object(orders_methods, "refund_money", new=AsyncMock()) as refund,
            patch.object(
                orders_methods,
                "set_performer_declined_order_status",
                new=AsyncMock(),
            ) as set_status,
        ):
            await orders_methods.performer_decline_order(1, 3)

        refund.assert_not_awaited()
        set_status.assert_not_awaited()

    async def test_performer_decline_data_allows_active_paid_status(self):
        session = FakeSession(
            execute_results=[
                FakeResult(
                    (
                        OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
                        2,
                        100,
                        "Order",
                        "10",
                        OrderPaymentStates.COMPLETED.value,
                        "client@example.com",
                        "+79990000000",
                    )
                )
            ],
            scalar_results=[True],
        )

        payment_operation_id, refund_data = await get_performer_decline_refund_data(
            session,
            1,
            3,
        )

        self.assertIsNone(payment_operation_id)
        self.assertEqual(refund_data.current_status, OrderStates.AWAITING_CLIENT_CONFIRMATION.value)

    async def test_client_harddecline_from_allowed_statuses(self):
        for status in (
            OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
            OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
        ):
            session = FakeSession(scalar_results=[True, status])
            with patch.object(orders_methods, "AsyncSessionLocal", return_value=session):
                await orders_methods.client_harddecline_order(1, 2)

            update_params = compiled_params(session.statements[-2])
            history_params = compiled_params(session.statements[-1])
            self.assertEqual(update_params["status"], OrderStates.AWAITING_CONFLICT.value)
            self.assertEqual(history_params["old_status"], status)
            self.assertEqual(history_params["new_status"], OrderStates.AWAITING_CONFLICT.value)

    async def test_performer_confirm_order_rejects_awaiting_payment(self):
        session = FakeSession(
            execute_results=[FakeResult((OrderStates.AWAITING_PAYMENT.value, 2))],
            scalar_results=[True],
        )
        with patch.object(orders_methods, "AsyncSessionLocal", return_value=session):
            with self.assertRaises(ValidationError):
                await orders_methods.performer_confirm_order(1, 3)

    async def test_client_harddecline_rejects_awaiting_payment(self):
        session = FakeSession(scalar_results=[True, OrderStates.AWAITING_PAYMENT.value])
        with patch.object(orders_methods, "AsyncSessionLocal", return_value=session):
            with self.assertRaises(ValidationError):
                await orders_methods.client_harddecline_order(1, 2)

    async def test_performer_conflict_order_rejects_not_awaiting_conflict(self):
        session = FakeSession(
            execute_results=[FakeResult((OrderStates.AWAITING_CLIENT_CONFIRMATION.value, 2))],
            scalar_results=[True],
        )
        with patch.object(orders_methods, "AsyncSessionLocal", return_value=session):
            with self.assertRaises(ValidationError):
                await orders_methods.performer_conflict_order(1, 3)


class OrderStatusSetterTest(unittest.IsolatedAsyncioTestCase):
    async def test_unpaid_decline_writes_history_completed_at_and_expired_payment(self):
        session = FakeSession()
        await set_softdeclined_order_status(
            session,
            1,
            OrderStates.AWAITING_PAYMENT.value,
            3,
        )

        update_sql = str(session.statements[0].compile())
        self.assertIn("completed_at", update_sql)
        self.assertEqual(
            compiled_params(session.statements[0])["status"],
            OrderStates.UNSUCCESSFUL_COMPLETION.value,
        )
        self.assertEqual(
            compiled_params(session.statements[1])["new_status"],
            OrderStates.UNSUCCESSFUL_COMPLETION.value,
        )
        self.assertEqual(
            compiled_params(session.statements[2])["payment_status"],
            OrderPaymentStates.EXPIRED.value,
        )

    async def test_refund_decline_waits_for_client_payout(self):
        session = FakeSession()
        await set_performer_declined_order_status(
            session,
            1,
            OrderStates.AWAITING_CONFLICT.value,
            3,
            "20",
        )

        update_sql = str(session.statements[0].compile())
        self.assertNotIn("completed_at", update_sql)
        self.assertEqual(
            compiled_params(session.statements[0])["status"],
            OrderStates.AWAITING_CLIENT_PAYOUT.value,
        )
        self.assertEqual(
            compiled_params(session.statements[1])["new_status"],
            OrderStates.AWAITING_CLIENT_PAYOUT.value,
        )
        self.assertEqual(
            compiled_params(session.statements[2])["revoke_status"],
            OrderPaymentStates.REGISTERED.value,
        )
        self.assertEqual(compiled_params(session.statements[2])["paygine_revoked_operation_id"], "20")

    async def test_client_refund_status_waits_for_client_payout(self):
        session = FakeSession()
        await set_client_refund_order_status(
            session,
            1,
            OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
            2,
            "20",
        )

        update_sql = str(session.statements[0].compile())
        self.assertNotIn("completed_at", update_sql)
        self.assertEqual(
            compiled_params(session.statements[0])["status"],
            OrderStates.AWAITING_CLIENT_PAYOUT.value,
        )
        self.assertEqual(
            compiled_params(session.statements[1])["new_status"],
            OrderStates.AWAITING_CLIENT_PAYOUT.value,
        )
        self.assertEqual(compiled_params(session.statements[2])["paygine_revoked_operation_id"], "20")

    async def test_refund_webhook_completes_unsuccessful_order_once(self):
        session = FakeSession()
        operation = WebhookOrderOperation(
            order_id=1,
            payment_data_id=10,
            order_status=OrderStates.AWAITING_CLIENT_PAYOUT.value,
            payment_status=OrderPaymentStates.COMPLETED.value,
            payout_status=None,
            revoke_status=OrderPaymentStates.REGISTERED.value,
            payment_operation_id=100,
            operation_type="refund",
        )

        await set_webhook_refund_completed(session, operation)

        update_sql = str(session.statements[0].compile())
        self.assertIn("completed_at", update_sql)
        self.assertEqual(
            compiled_params(session.statements[0])["status"],
            OrderStates.UNSUCCESSFUL_COMPLETION.value,
        )
        self.assertEqual(
            compiled_params(session.statements[1])["new_status"],
            OrderStates.UNSUCCESSFUL_COMPLETION.value,
        )
        self.assertEqual(
            compiled_params(session.statements[2])["revoke_status"],
            OrderPaymentStates.COMPLETED.value,
        )

    async def test_refund_webhook_duplicate_does_not_write_history_again(self):
        session = FakeSession()
        operation = WebhookOrderOperation(
            order_id=1,
            payment_data_id=10,
            order_status=OrderStates.UNSUCCESSFUL_COMPLETION.value,
            payment_status=OrderPaymentStates.COMPLETED.value,
            payout_status=None,
            revoke_status=OrderPaymentStates.COMPLETED.value,
            payment_operation_id=100,
            operation_type="refund",
        )

        await set_webhook_refund_completed(session, operation)

        self.assertEqual(session.statements, [])


if __name__ == "__main__":
    unittest.main()
