from __future__ import annotations

import json
import unittest
from urllib.parse import parse_qs, urlparse

from api.payments.auth_methods import build_signature
from api.payments.config import PAYGINE_BASE_URL, PAYGINE_SECTOR, SR_REF
from api.payments.payments_methods import generate_withdrow_link
from api.payments.utils.generate_withdrow_link_methods import (
    GENERATE_WITHDROW_LINK_ENDPOINT,
)
from api.schemas.schemas_v1 import GenerateWithdrowLinkRequest


REAL_GENERATE_WITHDROW_LINK_DATA = {
    "paygine_order_id": 13116913,
}


class GenerateWithdrowLinkIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_generate_withdrow_link_returns_paygine_url(self):
        """Генерируем ссылку на выплату средств исполнителю."""
        payment_data = GenerateWithdrowLinkRequest(**REAL_GENERATE_WITHDROW_LINK_DATA)

        withdrow_link = await generate_withdrow_link(payment_data)
        parsed_url = urlparse(withdrow_link)
        parsed_query = parse_qs(parsed_url.query)
        expected_signature = build_signature(
            (PAYGINE_SECTOR, payment_data.paygine_order_id, SR_REF)
        )

        print(json.dumps({"withdrow_link": withdrow_link}, ensure_ascii=False, indent=2))

        self.assertTrue(
            withdrow_link.startswith(
                f"{PAYGINE_BASE_URL.rstrip('/')}{GENERATE_WITHDROW_LINK_ENDPOINT}?"
            )
        )
        self.assertEqual(parsed_query["sector"], [PAYGINE_SECTOR])
        self.assertEqual(parsed_query["id"], [str(payment_data.paygine_order_id)])
        self.assertEqual(parsed_query["sd_ref"], [SR_REF])
        self.assertEqual(parsed_query["signature"], [expected_signature])


if __name__ == "__main__":
    unittest.main()
