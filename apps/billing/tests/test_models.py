from django.test import TestCase

from apps.billing.models import Subscription
from apps.billing.plans import PlanKey
from apps.organizations.models import Organization


class SubscriptionModelTests(TestCase):
    """Tests for the Subscription model."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        cls.subscription = Subscription.objects.create(
            organization=cls.organization,
            polar_customer_id="cust-1",
            polar_subscription_id="sub-1",
            polar_product_id="test-starter-id",
            plan_key=PlanKey.STARTER,
            amount=2900,
            currency="usd",
            status=Subscription.Status.ACTIVE,
        )

    def test_is_active_true_for_live_statuses(self) -> None:
        for status in (
            Subscription.Status.TRIALING,
            Subscription.Status.ACTIVE,
            Subscription.Status.PAST_DUE,
        ):
            self.subscription.status = status
            self.subscription.save(update_fields=["status"])
            self.assertTrue(self.subscription.is_active)

    def test_is_active_false_for_other_statuses(self) -> None:
        for status in (
            Subscription.Status.CANCELED,
            Subscription.Status.UNPAID,
            Subscription.Status.PAUSED,
        ):
            self.subscription.status = status
            self.subscription.save(update_fields=["status"])
            self.assertFalse(self.subscription.is_active)

    def test_plan_returns_catalog_entry(self) -> None:
        self.assertEqual(self.subscription.plan.key, PlanKey.STARTER)
        self.assertEqual(self.subscription.plan.name, "Starter")
