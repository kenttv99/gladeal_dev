from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError as PydanticValidationError

from api.enums.enums_v1 import AdminOrderStatusCategories, OrderPaymentStates, OrderStates
from api.exceptions import OrderExpiredError, PerformerEmailRequiredError, ValidationError
from api.schemas.schemas_v1 import (
    AdminCloseDisputeRequest,
    AdminCloseToPerformerRequest,
    AdminOrderResponse,
    CreateOrderRequest,
)
from api.utils import admins_methods, orders_methods
from api.utils.order_status_webhook_methods import (
    calculate_delayed_order_expire_in,
    get_webhook_payout_completed_order_status,
)
from workers.utils.order_expire_methods import expire_confirmed_order


class FakeResult:
    def __init__(self, row):
        self.row = row

    def one_or_none(self):
        return self.row


class FakeScalarResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, execute_results=None, scalar_results=None, row_results=None):
        self.execute_results = list(execute_results or [])
        self.scalar_results = list(scalar_results or [])
        self.row_results = list(row_results or [])
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

    async def scalars(self, statement):
        self.statements.append(statement)
        rows = self.row_results.pop(0) if self.row_results else []
        return FakeScalarResult(rows)


def future(hours: int = 1) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


class AdminSchemasContractTest(unittest.TestCase):
    def test_close_to_client_does_not_expose_performer_email(self):
        self.assertNotIn("performer_email", AdminCloseDisputeRequest.model_fields)
        self.assertIn("performer_email", AdminCloseToPerformerRequest.model_fields)

    def test_admin_order_item_has_title_and_expire_in(self):
        self.assertIn("title", AdminOrderResponse.model_fields)
        self.assertIn("expire_in", AdminOrderResponse.model_fields)


class CreateOrderExpireInValidationTest(unittest.TestCase):
    def test_create_order_rejects_past_expire_in(self):
        with self.assertRaises(PydanticValidationError):
            CreateOrderRequest.model_validate(
                {
                    "order_type": "free_deal",
                    "title": "Past deadline",
                    "customer_email": "client@example.com",
                    "price": "1000.00",
                    "expire_in": datetime.now(timezone.utc) - timedelta(minutes=1),
                    "violation_proof_requirements": "proof",
                }
            )


class ApproveOrderEmailTest(unittest.IsolatedAsyncioTestCase):
    @patch("api.utils.orders_methods.AsyncSessionLocal")
    async def test_approve_without_email_succeeds(self, mock_session_local):
        session = FakeSession(
            execute_results=[
                FakeResult(
                    (
                        OrderStates.AWAITING_PERFORMER.value,
                        None,
                        10,
                        future(),
                    )
                )
            ],
            scalar_results=[True, 1],
        )
        mock_session_local.return_value = session

        await orders_methods.approve_order(1, 20, None)

        payment_updates = [
            statement
            for statement in session.statements
            if "performer_email" in statement.compile().params
        ]
        self.assertEqual(
            payment_updates[0].compile().params["performer_email"],
            None,
        )

    @patch("api.utils.orders_methods.AsyncSessionLocal")
    async def test_approve_rejects_expired_order(self, mock_session_local):
        session = FakeSession(
            execute_results=[
                FakeResult(
                    (
                        OrderStates.AWAITING_PERFORMER.value,
                        None,
                        10,
                        datetime.now(timezone.utc) - timedelta(minutes=1),
                    )
                )
            ],
            scalar_results=[True],
        )
        mock_session_local.return_value = session

        with self.assertRaises(OrderExpiredError):
            await orders_methods.approve_order(1, 20, "performer@example.com")


class ClientConfirmWithoutEmailTest(unittest.IsolatedAsyncioTestCase):
    @patch("api.utils.orders_methods.set_client_confirmed_order_status", new_callable=AsyncMock)
    @patch("api.utils.orders_methods.register_payout_deal", new_callable=AsyncMock)
    @patch("api.utils.orders_methods.get_client_confirm_payment_data", new_callable=AsyncMock)
    @patch("api.utils.orders_methods.AsyncSessionLocal")
    async def test_client_confirm_defers_payout_without_email(
        self,
        mock_session_local,
        mock_get_confirm_data,
        mock_register_payout,
        mock_set_status,
    ):
        mock_session_local.return_value = FakeSession()
        mock_get_confirm_data.return_value = SimpleNamespace(
            current_status=OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
            performer_id=20,
            performer_email=None,
            performer_phone="+79997654321",
            price=Decimal("2500.00"),
            title="Design logo",
            paygine_payment_operation_id=123,
            payment_status=OrderPaymentStates.COMPLETED.value,
        )

        await orders_methods.client_confirm_order(order_id=1, client_id=10)

        mock_register_payout.assert_not_awaited()
        mock_set_status.assert_awaited_once()
        args = mock_set_status.await_args.args
        self.assertIsNone(args[4])
        self.assertIsNone(args[5])


class PayoutOperationRegistrationTest(unittest.IsolatedAsyncioTestCase):
    def _row(self, stored_email=None, payout_operation_id=None):
        return (
            OrderStates.AWAITING_PERFORMER_PAYOUT.value,
            Decimal("2500.00"),
            "Design logo",
            1,
            stored_email,
            123,
            OrderPaymentStates.COMPLETED.value,
            payout_operation_id,
            OrderPaymentStates.REGISTERED.value if payout_operation_id else None,
            "+79997654321",
        )

    @patch("api.utils.orders_methods.register_payout_deal", new_callable=AsyncMock)
    @patch("api.utils.orders_methods.AsyncSessionLocal")
    async def test_payout_link_saves_email_and_registers_payout(
        self,
        mock_session_local,
        mock_register_payout,
    ):
        mock_session_local.return_value = FakeSession(
            execute_results=[FakeResult(self._row())]
        )
        mock_register_payout.return_value = SimpleNamespace(
            payment_values=SimpleNamespace(
                paygine_payout_operation_id="777",
                expire_payout_at=future(),
            )
        )

        operation_id = await orders_methods.get_or_create_order_payout_operation_id(
            order_id=1,
            performer_id=20,
            performer_email="Performer@Example.com",
        )

        self.assertEqual(operation_id, 777)
        request = mock_register_payout.await_args.args[0]
        self.assertEqual(request.performer_email, "performer@example.com")

    @patch("api.utils.orders_methods.register_payout_deal", new_callable=AsyncMock)
    @patch("api.utils.orders_methods.AsyncSessionLocal")
    async def test_payout_link_requires_email(
        self,
        mock_session_local,
        mock_register_payout,
    ):
        mock_session_local.return_value = FakeSession(
            execute_results=[FakeResult(self._row())]
        )

        with self.assertRaises(PerformerEmailRequiredError):
            await orders_methods.get_or_create_order_payout_operation_id(1, 20)

        mock_register_payout.assert_not_awaited()

    @patch("api.utils.orders_methods.register_payout_deal", new_callable=AsyncMock)
    @patch("api.utils.orders_methods.AsyncSessionLocal")
    async def test_payout_link_is_idempotent_for_existing_payout(
        self,
        mock_session_local,
        mock_register_payout,
    ):
        mock_session_local.return_value = FakeSession(
            execute_results=[FakeResult(self._row(payout_operation_id="888"))]
        )

        operation_id = await orders_methods.get_or_create_order_payout_operation_id(
            1,
            20,
            "performer@example.com",
        )

        self.assertEqual(operation_id, 888)
        mock_register_payout.assert_not_awaited()


class PerformerConfirmExpireInTest(unittest.IsolatedAsyncioTestCase):
    @patch("api.utils.orders_methods.AsyncSessionLocal")
    async def test_confirm_rejects_expired_order(self, mock_session_local):
        mock_session_local.return_value = FakeSession(
            execute_results=[
                FakeResult(
                    (
                        OrderStates.AWAITING_PERFORMER_CONFIRMATION.value,
                        10,
                        datetime.now(timezone.utc) - timedelta(minutes=1),
                    )
                )
            ],
            scalar_results=[True],
        )

        with self.assertRaises(OrderExpiredError):
            await orders_methods.performer_confirm_order(1, 20)


class PaymentLinkExpireInTest(unittest.IsolatedAsyncioTestCase):
    @patch("api.utils.orders_methods.AsyncSessionLocal")
    async def test_payment_link_rejects_expired_order(self, mock_session_local):
        mock_session_local.return_value = FakeSession(
            execute_results=[
                FakeResult(
                    (
                        123,
                        OrderPaymentStates.REGISTERED.value,
                        OrderStates.AWAITING_PAYMENT.value,
                        20,
                        datetime.now(timezone.utc) - timedelta(minutes=1),
                    )
                )
            ]
        )

        with self.assertRaises(OrderExpiredError):
            await orders_methods.get_order_payment_operation_id(1, 10)


class AdminCloseToPerformerEmailTest(unittest.IsolatedAsyncioTestCase):
    @patch("api.utils.admins_methods.register_payout_deal", new_callable=AsyncMock)
    @patch("api.utils.admins_methods.AsyncSessionLocal")
    async def test_admin_can_close_to_performer_with_email_in_request(
        self,
        mock_session_local,
        mock_register_payout,
    ):
        mock_session_local.return_value = FakeSession(
            execute_results=[
                FakeResult(
                    (
                        OrderStates.OPEN_CONFLICT.value,
                        20,
                        Decimal("2500.00"),
                        "Design logo",
                        OrderPaymentStates.COMPLETED.value,
                        None,
                        None,
                        None,
                        "+79997654321",
                        123,
                    )
                )
            ]
        )
        mock_register_payout.return_value = SimpleNamespace(
            payment_values=SimpleNamespace(
                paygine_payout_operation_id="777",
                expire_payout_at=future(),
            )
        )

        await admins_methods.close_order_to_performer(
            1,
            99,
            "Work delivered fully per spec",
            "Performer@Example.com",
        )

        request = mock_register_payout.await_args.args[0]
        self.assertEqual(request.performer_email, "performer@example.com")


class AdminCloseToPerformerWithoutEmailTest(unittest.IsolatedAsyncioTestCase):
    @patch("api.utils.admins_methods.register_payout_deal", new_callable=AsyncMock)
    @patch("api.utils.admins_methods.AsyncSessionLocal")
    async def test_admin_close_without_email_moves_to_payout_state(
        self,
        mock_session_local,
        mock_register_payout,
    ):
        mock_session_local.return_value = FakeSession(
            execute_results=[
                FakeResult(
                    (
                        OrderStates.OPEN_CONFLICT.value,
                        20,
                        Decimal("2500.00"),
                        "Design logo",
                        OrderPaymentStates.COMPLETED.value,
                        None,
                        None,
                        None,
                        "+79997654321",
                        123,
                    )
                )
            ]
        )

        await admins_methods.close_order_to_performer(
            1,
            99,
            "Work delivered fully per spec",
        )

        mock_register_payout.assert_not_awaited()
        statuses = [
            statement.compile().params.get("status")
            for statement in mock_session_local.return_value.statements
        ]
        self.assertIn(OrderStates.AWAITING_PERFORMER_PAYOUT.value, statuses)


class WebhookArbiterPayoutStatusTest(unittest.TestCase):
    def test_awaiting_payout_with_arbitration_reason_finishes_as_arbiter_status(self):
        status = get_webhook_payout_completed_order_status(
            OrderStates.AWAITING_PERFORMER_PAYOUT.value,
            "Work delivered fully per spec",
        )
        self.assertEqual(
            status,
            OrderStates.CLOSED_BY_ARBITER_TO_PERFORMER.value,
        )

    def test_awaiting_payout_without_arbitration_reason_is_successful(self):
        status = get_webhook_payout_completed_order_status(
            OrderStates.AWAITING_PERFORMER_PAYOUT.value,
        )
        self.assertEqual(status, OrderStates.SUCCESSFUL_COMPLETION.value)


class WorkerEmailNormalizationTest(unittest.IsolatedAsyncioTestCase):
    @patch(
        "workers.utils.order_expire_methods.set_expired_order_payout_status",
        new_callable=AsyncMock,
    )
    @patch("workers.utils.order_expire_methods.register_payout_deal", new_callable=AsyncMock)
    @patch(
        "workers.utils.order_expire_methods.get_expired_payout_order_data",
        new_callable=AsyncMock,
    )
    async def test_worker_normalizes_performer_email_before_payout(
        self,
        mock_get_data,
        mock_register_payout,
        mock_set_payout_status,
    ):
        mock_get_data.return_value = SimpleNamespace(
            current_status=OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
            paygine_payment_operation_id=123,
            performer_id=20,
            performer_email=" Performer@Example.com ",
            performer_phone="+79997654321",
            price=Decimal("2500.00"),
            title="Design logo",
            payment_status=OrderPaymentStates.COMPLETED.value,
        )
        mock_register_payout.return_value = SimpleNamespace(
            payment_values=SimpleNamespace(
                paygine_payout_operation_id="777",
                expire_payout_at=future(),
            )
        )

        await expire_confirmed_order(FakeSession(), 1)

        request = mock_register_payout.await_args.args[0]
        self.assertEqual(request.performer_email, "performer@example.com")
        mock_set_payout_status.assert_awaited_once()


class WorkerWithoutEmailTest(unittest.IsolatedAsyncioTestCase):
    @patch(
        "workers.utils.order_expire_methods.set_expired_order_awaiting_payout_status",
        new_callable=AsyncMock,
    )
    @patch("workers.utils.order_expire_methods.register_payout_deal", new_callable=AsyncMock)
    @patch(
        "workers.utils.order_expire_methods.get_expired_payout_order_data",
        new_callable=AsyncMock,
    )
    async def test_worker_defers_payout_without_email(
        self,
        mock_get_data,
        mock_register_payout,
        mock_set_awaiting_status,
    ):
        mock_get_data.return_value = SimpleNamespace(
            current_status=OrderStates.AWAITING_CLIENT_CONFIRMATION.value,
            paygine_payment_operation_id=123,
            performer_id=20,
            performer_email=None,
            performer_phone="+79997654321",
            price=Decimal("2500.00"),
            title="Design logo",
            payment_status=OrderPaymentStates.COMPLETED.value,
        )

        await expire_confirmed_order(FakeSession(), 1)

        mock_register_payout.assert_not_awaited()
        mock_set_awaiting_status.assert_awaited_once()


class AdminGetOrdersFiltersTest(unittest.IsolatedAsyncioTestCase):
    @patch("api.utils.admins_methods.AsyncSessionLocal")
    async def test_admin_orders_return_title_expire_and_filters(self, mock_session_local):
        now = datetime.now(timezone.utc)
        order = SimpleNamespace(
            id=1,
            client_id=2,
            performer_id=3,
            status=OrderStates.AWAITING_PERFORMER,
            title="Test deal",
            created_at=now,
            expire_in=now + timedelta(hours=2),
            completed_at=None,
        )
        session = FakeSession(row_results=[[order]])
        mock_session_local.return_value = session

        response = await admins_methods.get_orders(
            orders_limit=20,
            search="Test",
            status_category=AdminOrderStatusCategories.ACTIVE.value,
            user_id=2,
        )

        self.assertEqual(response.items[0].title, "Test deal")
        self.assertEqual(response.items[0].expire_in, order.expire_in)
        statement = str(session.statements[0])
        self.assertIn("LIKE", statement)
        self.assertIn(" IN ", statement)
        self.assertIn(" OR ", statement)

    async def test_admin_orders_reject_status_and_category_together(self):
        with self.assertRaises(ValidationError):
            await admins_methods.get_orders(
                orders_limit=20,
                status=[OrderStates.AWAITING_PERFORMER],
                status_category=AdminOrderStatusCategories.ACTIVE.value,
            )


class LatePaymentExpireInTest(unittest.TestCase):
    def test_late_payment_never_leaves_deadline_in_the_past(self):
        payment_at = datetime.now(timezone.utc)
        created_at = payment_at - timedelta(hours=10)
        expire_in = created_at + timedelta(hours=2)

        result = calculate_delayed_order_expire_in(created_at, expire_in, payment_at)

        self.assertEqual(result, payment_at + timedelta(hours=2))
