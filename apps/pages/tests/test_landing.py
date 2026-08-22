from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.billing.prices import PlanPrice


class LandingPageViewTests(TestCase):
    """Tests for the landing page pricing section."""

    def test_renders_public_plans_with_live_prices(self) -> None:
        with mock.patch("apps.billing.prices.get_plan_price", return_value=PlanPrice(2900, "usd")):
            response = self.client.get(reverse("pages:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Starter")
        self.assertContains(response, "$29.00")
        self.assertContains(response, "/ month")

    def test_renders_price_less_when_price_unavailable(self) -> None:
        with mock.patch("apps.billing.prices.get_plan_price", return_value=None):
            response = self.client.get(reverse("pages:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Starter")
        self.assertNotContains(response, "/ month")
