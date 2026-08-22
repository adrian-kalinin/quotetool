from datetime import timedelta
from types import SimpleNamespace
from unittest import mock
from uuid import uuid4

from django.test import TestCase
from django.test import override_settings
from django.utils import timezone

from apps.billing.models import Subscription
from apps.billing.models import WebhookEvent
from apps.billing.plans import PlanKey
from apps.billing.services import UnprocessableEventError
from apps.billing.services import process_webhook_event
from apps.billing.services import sync_subscription_state
from apps.billing.services import upsert_subscription
from apps.billing.tests.helpers import make_customer_state
from apps.billing.tests.helpers import make_state_subscription
from apps.billing.tests.helpers import make_subscription
from apps.organizations.models import Organization


class UpsertSubscriptionTests(TestCase):
    """Tests for upsert_subscription."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")

    def create_row(
        self,
        *,
        status: str = Subscription.Status.ACTIVE,
        product_id: str = "test-starter-id",
        subscription_id: str = "sub-1",
    ) -> Subscription:
        return Subscription.objects.create(
            organization=self.organization,
            polar_customer_id="cust-1",
            polar_subscription_id=subscription_id,
            polar_product_id=product_id,
            plan_key=PlanKey.STARTER,
            amount=2900,
            currency="usd",
            status=status,
        )

    def test_upsert_creates_snapshot_for_new_subscription(self) -> None:
        sub = make_subscription(amount=2900, currency="usd")

        upsert_subscription(self.organization, sub, polar_customer_id="cust-1")

        row = Subscription.objects.get(organization=self.organization)
        self.assertEqual(row.plan_key, PlanKey.STARTER)
        self.assertEqual(row.polar_product_id, "test-starter-id")
        self.assertEqual(row.amount, 2900)
        self.assertEqual(row.currency, "usd")
        self.assertEqual(row.status, "active")
        self.assertEqual(row.polar_subscription_id, "sub-1")
        self.assertEqual(row.polar_customer_id, "cust-1")

    def test_upsert_updates_live_fields_without_touching_snapshot(self) -> None:
        self.create_row()
        period_end = timezone.now() + timedelta(days=30)
        sub = make_subscription(
            status=Subscription.Status.PAST_DUE,
            cancel_at_period_end=True,
            current_period_end=period_end,
            amount=3100,
        )

        upsert_subscription(self.organization, sub, polar_customer_id="cust-1")

        row = Subscription.objects.get(organization=self.organization)
        self.assertEqual(row.status, Subscription.Status.PAST_DUE)
        self.assertTrue(row.cancel_at_period_end)
        self.assertEqual(row.current_period_end, period_end)
        self.assertEqual(row.plan_key, PlanKey.STARTER)
        self.assertEqual(row.amount, 2900)

    def test_upsert_refreshes_snapshot_on_product_rotation(self) -> None:
        self.create_row()
        with override_settings(POLAR_PRODUCT_IDS={PlanKey.STARTER: "prod-starter-rotated"}):
            sub = make_subscription(product_id="prod-starter-rotated", amount=4900)

            upsert_subscription(self.organization, sub, polar_customer_id="cust-1")

        row = Subscription.objects.get(organization=self.organization)
        self.assertEqual(row.plan_key, PlanKey.STARTER)
        self.assertEqual(row.polar_product_id, "prod-starter-rotated")
        self.assertEqual(row.amount, 4900)

    def test_upsert_reuses_row_on_resubscribe(self) -> None:
        self.create_row(status=Subscription.Status.CANCELED)
        sub = make_subscription(subscription_id="sub-2", status=Subscription.Status.ACTIVE)

        upsert_subscription(self.organization, sub, polar_customer_id="cust-1")

        self.assertEqual(Subscription.objects.count(), 1)
        row = Subscription.objects.get(organization=self.organization)
        self.assertEqual(row.polar_subscription_id, "sub-2")
        self.assertEqual(row.status, Subscription.Status.ACTIVE)

    def test_upsert_logs_warning_when_live_subscription_id_changes(self) -> None:
        self.create_row()
        sub = make_subscription(subscription_id="sub-2")

        with self.assertLogs("apps.billing.services", level="WARNING"):
            upsert_subscription(self.organization, sub, polar_customer_id="cust-1")

    def test_upsert_raises_for_unknown_product_on_new_subscription(self) -> None:
        sub = make_subscription(product_id="prod-unknown")

        with self.assertRaises(UnprocessableEventError):
            upsert_subscription(self.organization, sub, polar_customer_id="cust-1")

    def test_upsert_raises_for_unknown_product_on_plan_switch(self) -> None:
        self.create_row()
        sub = make_subscription(product_id="prod-unknown")

        with self.assertRaises(UnprocessableEventError):
            upsert_subscription(self.organization, sub, polar_customer_id="cust-1")

    def test_upsert_keeps_snapshot_for_unmapped_product_when_product_unchanged(self) -> None:
        self.create_row(product_id="prod-removed", subscription_id="sub-old")

        sub = make_subscription(product_id="prod-removed", subscription_id="sub-old", status="active")
        upsert_subscription(self.organization, sub, polar_customer_id="cust-1")

        row = Subscription.objects.get(organization=self.organization)
        self.assertEqual(row.plan_key, PlanKey.STARTER)


class ProcessWebhookEventTests(TestCase):
    """Tests for process_webhook_event idempotency and error handling."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")

    def process(self, event_id: str, data: object, event_type: str = "subscription.created") -> None:
        process_webhook_event(
            event_id=event_id,
            event_type=event_type,
            payload={"type": event_type},
            data=data,
        )

    def test_creates_processed_row_and_subscription(self) -> None:
        sub = make_subscription(external_id=str(self.organization.uuid))

        self.process("evt-1", sub)

        row = WebhookEvent.objects.get(polar_event_id="evt-1")
        self.assertEqual(row.status, WebhookEvent.Status.PROCESSED)
        self.assertEqual(row.event_type, "subscription.created")
        self.assertTrue(Subscription.objects.filter(organization=self.organization).exists())

    def test_duplicate_processed_event_is_skipped(self) -> None:
        sub = make_subscription(external_id=str(self.organization.uuid))
        self.process("evt-1", sub)
        Subscription.objects.filter(organization=self.organization).update(status=Subscription.Status.CANCELED)

        self.process("evt-1", sub)

        self.assertEqual(WebhookEvent.objects.filter(polar_event_id="evt-1").count(), 1)
        row = Subscription.objects.get(organization=self.organization)
        self.assertEqual(row.status, Subscription.Status.CANCELED)

    def test_records_unhandled_event_without_processing(self) -> None:
        self.process("evt-1", None, event_type="order.paid")

        row = WebhookEvent.objects.get(polar_event_id="evt-1")
        self.assertEqual(row.status, WebhookEvent.Status.RECEIVED)
        self.assertEqual(row.event_type, "order.paid")
        self.assertEqual(Subscription.objects.count(), 0)

    def test_duplicate_received_event_is_skipped(self) -> None:
        self.process("evt-1", None, event_type="order.paid")
        self.process("evt-1", None, event_type="order.paid")

        self.assertEqual(WebhookEvent.objects.filter(polar_event_id="evt-1").count(), 1)

    def test_error_row_reprocesses_on_redelivery(self) -> None:
        external_id = str(uuid4())
        sub = make_subscription(external_id=external_id)

        self.process("evt-1", sub)
        row = WebhookEvent.objects.get(polar_event_id="evt-1")
        self.assertEqual(row.status, WebhookEvent.Status.ERROR)
        self.assertIn("Unknown organization", row.error)

        organization = Organization.objects.create(name="Late Org.", uuid=external_id)
        self.process("evt-1", sub)

        row.refresh_from_db()
        self.assertEqual(row.status, WebhookEvent.Status.PROCESSED)
        self.assertEqual(row.error, "")
        self.assertTrue(Subscription.objects.filter(organization=organization).exists())

    def test_unknown_org_records_error_without_raising(self) -> None:
        sub = make_subscription(external_id=str(uuid4()))

        self.process("evt-1", sub)

        row = WebhookEvent.objects.get(polar_event_id="evt-1")
        self.assertEqual(row.status, WebhookEvent.Status.ERROR)
        self.assertEqual(Subscription.objects.count(), 0)

    def test_transient_failure_rolls_back_row_and_raises(self) -> None:
        sub = make_subscription(external_id=str(self.organization.uuid))

        with (
            mock.patch("apps.billing.services.handle_subscription_event", side_effect=RuntimeError("boom")),
            self.assertRaises(RuntimeError),
        ):
            self.process("evt-1", sub)

        self.assertFalse(WebhookEvent.objects.filter(polar_event_id="evt-1").exists())
        self.assertEqual(Subscription.objects.count(), 0)


class SyncSubscriptionStateTests(TestCase):
    """Tests for sync_subscription_state (checkout return race handling)."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")

    def test_syncs_from_active_subscriptions(self) -> None:
        sub = make_state_subscription()
        state = make_customer_state(active_subscriptions=[sub])
        client = SimpleNamespace(customers=SimpleNamespace(get_state_external=mock.Mock(return_value=state)))

        with mock.patch("apps.billing.services.get_polar_client", return_value=client):
            sync_subscription_state(self.organization)

        row = Subscription.objects.get(organization=self.organization)
        self.assertEqual(row.polar_customer_id, "cust-1")

    def test_api_failure_is_silent(self) -> None:
        client = SimpleNamespace(
            customers=SimpleNamespace(get_state_external=mock.Mock(side_effect=RuntimeError("down")))
        )

        with mock.patch("apps.billing.services.get_polar_client", return_value=client):
            sync_subscription_state(self.organization)

        self.assertEqual(Subscription.objects.count(), 0)

    def test_unknown_product_is_skipped(self) -> None:
        sub = make_state_subscription(product_id="prod-unknown")
        state = make_customer_state(active_subscriptions=[sub])
        client = SimpleNamespace(customers=SimpleNamespace(get_state_external=mock.Mock(return_value=state)))

        with mock.patch("apps.billing.services.get_polar_client", return_value=client):
            sync_subscription_state(self.organization)

        self.assertEqual(Subscription.objects.count(), 0)
