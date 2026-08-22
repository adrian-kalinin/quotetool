from django.test import TestCase

from apps.billing.models import Subscription
from apps.billing.plans import PlanKey
from apps.organizations.models import Organization


class OrganizationModelTests(TestCase):
    """Tests for the Organization model."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")

    def test_has_active_subscription_false_without_subscription(self) -> None:
        self.assertFalse(self.organization.has_active_subscription)

    def test_has_active_subscription_true_for_active_subscription(self) -> None:
        Subscription.objects.create(
            organization=self.organization,
            polar_customer_id="cust-1",
            polar_subscription_id="sub-1",
            polar_product_id="test-starter-id",
            plan_key=PlanKey.STARTER,
            amount=2900,
            currency="usd",
            status=Subscription.Status.ACTIVE,
        )

        self.assertTrue(self.organization.has_active_subscription)

    def test_has_active_subscription_false_for_inactive_subscription(self) -> None:
        Subscription.objects.create(
            organization=self.organization,
            polar_customer_id="cust-1",
            polar_subscription_id="sub-1",
            polar_product_id="test-starter-id",
            plan_key=PlanKey.STARTER,
            amount=2900,
            currency="usd",
            status=Subscription.Status.CANCELED,
        )

        self.assertFalse(self.organization.has_active_subscription)
