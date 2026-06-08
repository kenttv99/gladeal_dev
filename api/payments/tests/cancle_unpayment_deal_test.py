from __future__ import annotations

import json
import unittest

from api.exceptions import PaymentInvalidProviderResponseError
from api.payments.payments_methods import cancle_unpayment_deal
from api.schemas.schemas_v1 import CancleUnpaymentDealRequest


REAL_CANCLE_UNPAYMENT_DEAL_DATA = {
    "paygine_order_id": 13098226,
}


class CancleUnpaymentDealIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_cancle_unpayment_deal_returns_readable_paygine_response(self):
        """Переводим существующий заказ в ПЦ в EXPIRED."""
        payment_data = CancleUnpaymentDealRequest(**REAL_CANCLE_UNPAYMENT_DEAL_DATA)

        try:
            response = await cancle_unpayment_deal(payment_data)
        except PaymentInvalidProviderResponseError as exc:
            self.fail(f"Paygine cancle response parse error: {exc.details}")

        print(json.dumps(response, ensure_ascii=False, indent=2))

        self.assertIn("root_tag", response)
        self.assertIn("data", response)
        self.assertIsInstance(response["root_tag"], str)


if __name__ == "__main__":
    unittest.main()
