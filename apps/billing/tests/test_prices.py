from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.test import override_settings

from apps.billing.plans import PlanKey
from apps.billing.prices import PlanPrice
from apps.billing.prices import get_plan_price
from apps.billing.tests.helpers import make_custom_price
from apps.billing.tests.helpers import make_fixed_price
from apps.billing.tests.helpers import make_product


class GetPlanPriceTests(TestCase):
    """Tests for get_plan_price caching and degradation."""

    def setUp(self) -> None:
        cache.clear()

    def test_returns_none_when_plan_not_sellable(self) -> None:
        with override_settings(POLAR_PRODUCT_IDS={}):
            self.assertIsNone(get_plan_price(PlanKey.STARTER))

    def test_fetches_price_and_caches(self) -> None:
        product = make_product(prices=[make_fixed_price()])
        client = SimpleNamespace(products=SimpleNamespace(get=mock.Mock(return_value=product)))

        with mock.patch("apps.billing.prices.get_polar_client", return_value=client):
            price = get_plan_price(PlanKey.STARTER)
            price_again = get_plan_price(PlanKey.STARTER)

        self.assertEqual(price, PlanPrice(amount_cents=2900, currency="usd"))
        self.assertEqual(price_again, price)
        self.assertEqual(client.products.get.call_count, 1)

    def test_skips_archived_prices(self) -> None:
        product = make_product(prices=[make_fixed_price(amount=9900, is_archived=True)])
        client = SimpleNamespace(products=SimpleNamespace(get=mock.Mock(return_value=product)))

        with mock.patch("apps.billing.prices.get_polar_client", return_value=client):
            price = get_plan_price(PlanKey.STARTER)

        self.assertIsNone(price)

    def test_serves_stale_on_api_failure(self) -> None:
        stale = PlanPrice(amount_cents=1900, currency="usd")
        cache.set("billing:price-stale:test-starter-id", stale, timeout=None)
        client = SimpleNamespace(products=SimpleNamespace(get=mock.Mock(side_effect=RuntimeError("down"))))

        with (
            mock.patch("apps.billing.prices.get_polar_client", return_value=client),
            self.assertLogs("apps.billing.prices", level="ERROR") as logs,
        ):
            price = get_plan_price(PlanKey.STARTER)

        self.assertEqual(price, stale)
        self.assertIn("Failed to fetch product from Polar API", logs.output[0])

    def test_returns_none_on_api_failure_without_stale(self) -> None:
        client = SimpleNamespace(products=SimpleNamespace(get=mock.Mock(side_effect=RuntimeError("down"))))

        with (
            mock.patch("apps.billing.prices.get_polar_client", return_value=client),
            self.assertLogs("apps.billing.prices", level="ERROR") as logs,
        ):
            price = get_plan_price(PlanKey.STARTER)

        self.assertIsNone(price)
        self.assertIn("Failed to fetch product from Polar API", logs.output[0])

    def test_returns_none_when_no_fixed_price(self) -> None:
        product = make_product(prices=[make_custom_price()])
        client = SimpleNamespace(products=SimpleNamespace(get=mock.Mock(return_value=product)))

        with mock.patch("apps.billing.prices.get_polar_client", return_value=client):
            price = get_plan_price(PlanKey.STARTER)

        self.assertIsNone(price)
