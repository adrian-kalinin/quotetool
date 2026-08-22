from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from polar.v2026_04.webhooks import PolarWebhookError
from polar.v2026_04.webhooks import PolarWebhookUnknownTypeError
from polar.v2026_04.webhooks import PolarWebhookVerificationError
from polar.v2026_04.webhooks import WebhookProductUpdatedPayload
from polar.v2026_04.webhooks import WebhookSubscriptionCreatedPayload

from apps.accounts.models import User
from apps.billing.models import Subscription
from apps.billing.models import WebhookEvent
from apps.billing.plans import PlanKey
from apps.billing.prices import PlanPrice
from apps.billing.tests.helpers import make_customer_state
from apps.billing.tests.helpers import make_product
from apps.billing.tests.helpers import make_state_subscription
from apps.billing.tests.helpers import make_subscription
from apps.organizations.models import Organization
from apps.organizations.models import OrganizationMembership

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse


class BillingViewTestCase(TestCase):
    """Base setup: one organization with an owner and a member."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        cls.owner = cls.create_user("owner@example.com", OrganizationMembership.Role.OWNER)
        cls.member = cls.create_user("member@example.com", OrganizationMembership.Role.MEMBER)

    @classmethod
    def create_user(cls, email: str, role: str) -> User:
        user = User.objects.create_user(email, "test-password")
        user.active_organization = cls.organization
        user.save(update_fields=["active_organization"])
        OrganizationMembership.objects.create(user=user, organization=cls.organization, role=role)
        return user

    def create_subscription(self, *, status: str = Subscription.Status.ACTIVE) -> Subscription:
        return Subscription.objects.create(
            organization=self.organization,
            polar_customer_id="cust-1",
            polar_subscription_id="sub-1",
            polar_product_id="test-starter-id",
            plan_key=PlanKey.STARTER,
            amount=2900,
            currency="usd",
            status=status,
        )

    def mock_client(self) -> mock.Mock:
        return mock.Mock()


class BillingSettingsViewTests(BillingViewTestCase):
    """Tests for the billing settings page."""

    def test_renders_no_subscription_state_for_non_manager(self) -> None:
        self.client.force_login(self.member)
        with mock.patch("apps.billing.prices.get_plan_price", return_value=PlanPrice(2900, "usd")):
            response = self.client.get(reverse("billing:settings-billing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your organization doesn't have an active subscription")

    def test_renders_subscription_and_portal_for_manager(self) -> None:
        self.create_subscription()
        self.client.force_login(self.owner)
        with mock.patch("apps.billing.prices.get_plan_price", return_value=PlanPrice(2900, "usd")):
            response = self.client.get(reverse("billing:settings-billing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Starter")
        self.assertContains(response, "Manage in portal")
        self.assertContains(response, "$29.00 / month")

    def test_canceled_subscription_shows_no_renewal_message(self) -> None:
        subscription = self.create_subscription(status=Subscription.Status.CANCELED)
        subscription.current_period_end = timezone.now() + timedelta(days=30)
        subscription.cancel_at_period_end = True
        subscription.save(update_fields=["current_period_end", "cancel_at_period_end"])
        self.client.force_login(self.owner)
        with mock.patch("apps.billing.prices.get_plan_price", return_value=PlanPrice(2900, "usd")):
            response = self.client.get(reverse("billing:settings-billing"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "will renew on")
        self.assertNotContains(response, "valid until")
        self.assertContains(response, "Canceled")


class CheckoutViewTests(BillingViewTestCase):
    """Tests for the hosted checkout flow."""

    def test_creates_checkout_and_redirects_303_for_manager(self) -> None:
        self.client.force_login(self.owner)
        client = self.mock_client()
        client.checkouts.create.return_value = SimpleNamespace(url="https://polar.sh/c/abc")

        with mock.patch("apps.billing.views.checkout.get_polar_client", return_value=client):
            response = self.client.post(reverse("billing:checkout"), {"plan_key": "starter"})

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response["Location"], "https://polar.sh/c/abc")
        client.checkouts.create.assert_called_once()
        kwargs = client.checkouts.create.call_args.kwargs
        self.assertEqual(kwargs["products"], ["test-starter-id"])
        self.assertEqual(kwargs["external_customer_id"], str(self.organization.uuid))

    def test_blocks_non_manager(self) -> None:
        self.client.force_login(self.member)

        with mock.patch("apps.billing.views.checkout.get_polar_client") as client:
            response = self.client.post(reverse("billing:checkout"), {"plan_key": "starter"})

        self.assertEqual(response.status_code, 403)
        client.checkouts.create.assert_not_called()

    def test_redirects_to_settings_when_active_subscription(self) -> None:
        self.create_subscription()
        self.client.force_login(self.owner)

        with mock.patch("apps.billing.views.checkout.get_polar_client") as client:
            response = self.client.post(reverse("billing:checkout"), {"plan_key": "starter"})

        self.assertRedirects(response, reverse("billing:settings-billing"), fetch_redirect_response=False)
        client.checkouts.create.assert_not_called()

    def test_redirects_on_invalid_plan_key(self) -> None:
        self.client.force_login(self.owner)

        with mock.patch("apps.billing.views.checkout.get_polar_client") as client:
            response = self.client.post(reverse("billing:checkout"), {"plan_key": "bogus"})

        self.assertRedirects(response, reverse("billing:settings-billing"), fetch_redirect_response=False)
        client.checkouts.create.assert_not_called()

    def test_handles_api_failure_gracefully(self) -> None:
        self.client.force_login(self.owner)
        client = self.mock_client()
        client.checkouts.create.side_effect = RuntimeError("down")

        with (
            mock.patch("apps.billing.views.checkout.get_polar_client", return_value=client),
            self.assertLogs("apps.billing.views.checkout", level="ERROR") as logs,
        ):
            response = self.client.post(reverse("billing:checkout"), {"plan_key": "starter"})

        self.assertRedirects(response, reverse("billing:settings-billing"), fetch_redirect_response=False)
        self.assertIn("Failed to create Polar checkout", logs.output[0])


class CheckoutSuccessViewTests(BillingViewTestCase):
    """Tests for the checkout return race handling."""

    def test_syncs_and_redirects_to_settings(self) -> None:
        self.client.force_login(self.owner)
        sub = make_state_subscription()
        state = make_customer_state(active_subscriptions=[sub])
        client = SimpleNamespace(customers=SimpleNamespace(get_state_external=mock.Mock(return_value=state)))

        with mock.patch("apps.billing.services.get_polar_client", return_value=client):
            response = self.client.get(reverse("billing:checkout-success"))

        self.assertRedirects(response, reverse("billing:settings-billing"), fetch_redirect_response=False)
        self.assertTrue(Subscription.objects.filter(organization=self.organization).exists())

    def test_redirects_even_when_api_fails(self) -> None:
        self.client.force_login(self.owner)
        client = SimpleNamespace(
            customers=SimpleNamespace(get_state_external=mock.Mock(side_effect=RuntimeError("down")))
        )

        with mock.patch("apps.billing.services.get_polar_client", return_value=client):
            response = self.client.get(reverse("billing:checkout-success"))

        self.assertRedirects(response, reverse("billing:settings-billing"), fetch_redirect_response=False)


class PortalRedirectViewTests(BillingViewTestCase):
    """Tests for the customer portal redirect."""

    def test_redirects_to_customer_portal_for_manager(self) -> None:
        self.client.force_login(self.owner)
        client = self.mock_client()
        client.customer_sessions.create.return_value = SimpleNamespace(customer_portal_url="https://polar.sh/portal/x")

        with mock.patch("apps.billing.views.portal.get_polar_client", return_value=client):
            response = self.client.post(reverse("billing:portal"))

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response["Location"], "https://polar.sh/portal/x")
        kwargs = client.customer_sessions.create.call_args.kwargs
        self.assertEqual(kwargs["customer_external_id"], str(self.organization.uuid))

    def test_blocks_non_manager(self) -> None:
        self.client.force_login(self.member)

        with mock.patch("apps.billing.views.portal.get_polar_client") as client:
            response = self.client.post(reverse("billing:portal"))

        self.assertEqual(response.status_code, 403)
        client.customer_sessions.create.assert_not_called()

    def test_handles_api_failure_gracefully(self) -> None:
        self.client.force_login(self.owner)
        client = self.mock_client()
        client.customer_sessions.create.side_effect = RuntimeError("down")

        with (
            mock.patch("apps.billing.views.portal.get_polar_client", return_value=client),
            self.assertLogs("apps.billing.views.portal", level="ERROR") as logs,
        ):
            response = self.client.post(reverse("billing:portal"))

        self.assertRedirects(response, reverse("billing:settings-billing"), fetch_redirect_response=False)
        self.assertIn("Failed to create Polar customer session", logs.output[0])


class WebhookViewTests(BillingViewTestCase):
    """Tests for webhook verification and response policy."""

    def post(self, body: str = '{"type": "subscription.created"}') -> "_MonkeyPatchedWSGIResponse":
        return self.client.post(
            reverse("billing:webhook"),
            data=body,
            content_type="application/json",
            HTTP_WEBHOOK_ID="evt-1",
            HTTP_WEBHOOK_TIMESTAMP="1700000000",
            HTTP_WEBHOOK_SIGNATURE="v1,abc",
        )

    def test_rejects_bad_signature_with_403(self) -> None:
        with mock.patch(
            "apps.billing.views.webhook.validate_event", side_effect=PolarWebhookVerificationError("bad signature")
        ):
            response = self.post()

        self.assertEqual(response.status_code, 403)

    def test_acks_unknown_event_types_with_200(self) -> None:
        with mock.patch(
            "apps.billing.views.webhook.validate_event",
            side_effect=PolarWebhookUnknownTypeError("subscription.mystery"),
        ):
            response = self.post()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(WebhookEvent.objects.count(), 0)

    def test_rejects_malformed_payload_with_400(self) -> None:
        with mock.patch("apps.billing.views.webhook.validate_event", side_effect=PolarWebhookError("bad payload")):
            response = self.post()

        self.assertEqual(response.status_code, 400)

    def test_records_non_subscription_events_with_200(self) -> None:
        event = WebhookProductUpdatedPayload(
            type="product.updated",
            timestamp="2025-01-01T00:00:00Z",
            data=make_product(),
        )

        with mock.patch("apps.billing.views.webhook.validate_event", return_value=event):
            response = self.post(body='{"type": "product.updated"}')

        self.assertEqual(response.status_code, 200)
        row = WebhookEvent.objects.get()
        self.assertEqual(row.status, WebhookEvent.Status.RECEIVED)
        self.assertEqual(row.event_type, "product.updated")
        self.assertEqual(Subscription.objects.count(), 0)

    def test_processes_subscription_event(self) -> None:
        event = WebhookSubscriptionCreatedPayload(
            type="subscription.created",
            timestamp="2025-01-01T00:00:00Z",
            data=make_subscription(external_id=str(self.organization.uuid)),
        )

        with mock.patch("apps.billing.views.webhook.validate_event", return_value=event):
            response = self.post()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(WebhookEvent.objects.count(), 1)
        self.assertTrue(Subscription.objects.filter(organization=self.organization).exists())

    def test_returns_500_on_transient_failure(self) -> None:
        event = WebhookSubscriptionCreatedPayload(
            type="subscription.created",
            timestamp="2025-01-01T00:00:00Z",
            data=make_subscription(external_id=str(self.organization.uuid)),
        )

        with (
            mock.patch("apps.billing.views.webhook.validate_event", return_value=event),
            mock.patch("apps.billing.services.handle_subscription_event", side_effect=RuntimeError("boom")),
            self.assertLogs("apps.billing.views.webhook", level="ERROR") as logs,
        ):
            response = self.post()

        self.assertEqual(response.status_code, 500)
        self.assertEqual(WebhookEvent.objects.count(), 0)
        self.assertIn("Failed to process webhook event", logs.output[0])

    def test_duplicate_delivery_is_acked_and_skipped(self) -> None:
        event = WebhookSubscriptionCreatedPayload(
            type="subscription.created",
            timestamp="2025-01-01T00:00:00Z",
            data=make_subscription(external_id=str(self.organization.uuid)),
        )

        with mock.patch("apps.billing.views.webhook.validate_event", return_value=event):
            first = self.post()
            second = self.post()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(WebhookEvent.objects.count(), 1)
        self.assertEqual(Subscription.objects.count(), 1)
