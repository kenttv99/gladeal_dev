from __future__ import annotations

import unittest
from decimal import Decimal

from api.payments.utils.commission_methods import calculate_payment_amounts, from_kopecks


class CalculatePaymentAmountsTest(unittest.TestCase):
    def test_calculate_payment_amounts_returns_amounts(self):
        payment_amounts = calculate_payment_amounts(Decimal("10000.00"))

        self.assertEqual(
            list(payment_amounts),
            ["total_amount_with_fee", "order_amount", "service_fee_amount"],
        )
        self.assertEqual(payment_amounts["total_amount_with_fee"], 1085000)
        self.assertEqual(payment_amounts["order_amount"], 1000000)
        self.assertEqual(payment_amounts["service_fee_amount"], 85000)

    def test_calculate_payment_amounts_truncates_fee_to_kopecks(self):
        payment_amounts = calculate_payment_amounts(Decimal("10000.067"))

        self.assertEqual(payment_amounts["service_fee_amount"], 85000)
        self.assertEqual(payment_amounts["order_amount"], 1000006)
        self.assertEqual(payment_amounts["total_amount_with_fee"], 1085007)

    def test_from_kopecks_returns_rubles(self):
        self.assertEqual(from_kopecks(1085000), Decimal("10850"))


if __name__ == "__main__":
    unittest.main()
