from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import unittest

from api.enums.enums_v1 import OrderStates, OrderTypes
from api.schemas.schemas_v1 import (
    AdminOrderInfoResponse,
    AdminOrderStatusHistoryResponse,
    CreateOrderRequest,
    OrderInfoResponse,
)
from database.models.orders import Order


class OrderSchemasTest(unittest.TestCase):
    def test_create_order_request_minimal(self):
        now = datetime.now(timezone.utc)
        data = {
            "order_type": "free_deal",
            "title": "Minimal Deal",
            "customer_email": "client@example.com",
            "price": "5000.00",
            "expire_in": now,
            "violation_proof_requirements": "proof_1, proof_2",
        }
        req = CreateOrderRequest.model_validate(data)
        self.assertEqual(req.order_type, OrderTypes.FREE_DEAL)
        self.assertEqual(req.title, "Minimal Deal")
        self.assertEqual(req.price, Decimal("5000.00"))
        self.assertIsNone(req.source_of_truth)
        self.assertIsNone(req.site_or_app)
        self.assertIsNone(req.customer_identity)
        self.assertIsNone(req.additional_requirements)
        self.assertIsNone(req.contact_free_deal)
        self.assertIsNone(req.task_free_deal)
        self.assertIsNone(req.how_to_proove_free_deal)

    def test_create_order_request_full(self):
        now = datetime.now(timezone.utc)
        data = {
            "order_type": "subscriptions",
            "title": "Subscription Deal",
            "customer_email": "client@example.com",
            "price": "10000.00",
            "expire_in": now,
            "violation_proof_requirements": "screenshots, chat logs",
            "source_of_truth": "Service Admin Panel",
            "site_or_app": "https://example.com",
            "customer_identity": "ID-12345",
            "additional_requirements": "Must activate within 2 hours",
            "contact_free_deal": "@contact",
            "task_free_deal": "Task details",
            "how_to_proove_free_deal": "Confirmation email",
        }
        req = CreateOrderRequest.model_validate(data)
        self.assertEqual(req.order_type, OrderTypes.SUBSCRIPTIONS)
        self.assertEqual(req.source_of_truth, "Service Admin Panel")
        self.assertEqual(req.site_or_app, "https://example.com")
        self.assertEqual(req.customer_identity, "ID-12345")
        self.assertEqual(req.additional_requirements, "Must activate within 2 hours")
        self.assertEqual(req.contact_free_deal, "@contact")
        self.assertEqual(req.task_free_deal, "Task details")
        self.assertEqual(req.how_to_proove_free_deal, "Confirmation email")

    def test_order_info_response_from_orm_order(self):
        now = datetime.now(timezone.utc)
        order = Order(
            id=10,
            client_id=1,
            performer_id=2,
            order_type=OrderTypes.TICKETS_AND_RESERVATIONS,
            title="Concert Tickets",
            source_of_truth="Kassir.ru",
            site_or_app="https://kassir.ru",
            customer_identity="client@example.com",
            violation_proof_requirements="e-tickets",
            additional_requirements=None,
            contact_free_deal=None,
            task_free_deal=None,
            how_to_proove_free_deal=None,
            slug="concert-tickets-slug",
            price=Decimal("15000.00"),
            status=OrderStates.AWAITING_PERFORMER,
            created_at=now,
            updated_at=now,
            expire_in=now,
            completed_at=None,
        )
        res = OrderInfoResponse.model_validate(order)
        self.assertEqual(res.id, 10)
        self.assertEqual(res.order_type, "tickets_and_reservations")
        self.assertEqual(res.source_of_truth, "Kassir.ru")
        self.assertEqual(res.slug, "concert-tickets-slug")
        self.assertIsNone(res.additional_requirements)

    def test_admin_order_info_response_from_orm(self):
        now = datetime.now(timezone.utc)
        admin_res = AdminOrderInfoResponse(
            id=10,
            client_id=1,
            performer_id=2,
            order_type=OrderTypes.FREE_DEAL,
            title="Custom Job",
            source_of_truth=None,
            site_or_app=None,
            customer_identity=None,
            violation_proof_requirements="github PR",
            additional_requirements=None,
            contact_free_deal="@dev",
            task_free_deal="Write code",
            how_to_proove_free_deal="PR merged",
            slug="custom-job-slug",
            price=Decimal("20000.00"),
            status=OrderStates.SUCCESSFUL_COMPLETION,
            checked_by_worker_at=now,
            expire_in=now,
            created_at=now,
            updated_at=now,
            completed_at=now,
            status_history=[],
        )
        self.assertEqual(admin_res.order_type, "free_deal")
        self.assertEqual(admin_res.task_free_deal, "Write code")


if __name__ == "__main__":
    unittest.main()
