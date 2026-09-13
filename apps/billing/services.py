import logging
from typing import cast

from django.core.exceptions import ValidationError
from django.db import transaction
from polar.v2026_04.outputs import CustomerStateSubscription
from polar.v2026_04.outputs import Subscription as PolarSubscription

from apps.billing.client import get_polar_client
from apps.billing.models import Subscription
from apps.billing.models import WebhookEvent
from apps.billing.plans import resolve_plan
from apps.organizations.models import Organization

logger = logging.getLogger(__name__)


class UnprocessableEventError(Exception):
    """Raised by handlers when a delivery can never succeed; recorded as ERROR and acked, so Polar does not retry."""


def process_webhook_event(*, event_id: str, event_type: str, payload: dict, data: object) -> None:
    """Record every verified delivery; apply known event types idempotently. DB-only, no external calls.

    Deliveries with no handler are stored with status=RECEIVED so they can be reprocessed
    later. Handlers raise UnprocessableEventError for permanent failures: recorded as ERROR and
    acked (200). Transient errors propagate and roll back the row, so Polar's retry processes fresh.
    """
    with transaction.atomic():
        row, created = WebhookEvent.objects.get_or_create(
            polar_event_id=event_id,
            defaults={
                "event_type": event_type,
                "payload": payload,
                "status": WebhookEvent.Status.RECEIVED,
                "error": "",
            },
        )

        # A concurrent delivery may have inserted the same event; lock the winner's row
        # so only unprocessed/error rows are (re)applied.
        if not created:
            row = WebhookEvent.objects.select_for_update().get(pk=row.pk)

            if row.status != WebhookEvent.Status.ERROR:
                return

        try:
            status, error = _dispatch_event(event_type, data), ""
        except UnprocessableEventError as exc:
            status, error = WebhookEvent.Status.ERROR, str(exc)

        row.status = status
        row.error = error
        row.save(update_fields=["status", "error"])


def _dispatch_event(event_type: str, data: object) -> WebhookEvent.Status:
    """Dispatch to the handler for this event family; RECEIVED when there is none."""
    if event_type.startswith("subscription."):
        handle_subscription_event(cast("PolarSubscription", data))
        return WebhookEvent.Status.PROCESSED

    return WebhookEvent.Status.RECEIVED


def handle_subscription_event(subscription: PolarSubscription) -> None:
    """Resolve the organization from customer.external_id, then apply the subscription."""
    external_id = subscription.customer.external_id

    if not external_id:
        raise UnprocessableEventError("Missing customer.external_id in webhook payload.")

    try:
        organization = Organization.objects.get(uuid=external_id)
    except Organization.DoesNotExist:
        raise UnprocessableEventError(f"Unknown organization uuid: {external_id}") from None
    except (ValueError, ValidationError):
        raise UnprocessableEventError(f"Invalid organization uuid: {external_id}") from None

    upsert_subscription(organization, subscription, polar_customer_id=subscription.customer_id)


def upsert_subscription(
    organization: Organization,
    subscription: PolarSubscription | CustomerStateSubscription,
    *,
    polar_customer_id: str,
) -> None:
    """Upsert the org's subscription from a webhook or customer-state subscription.

    Keyed on the organization — the business rule is one subscription per org, so a
    cancel-then-resubscribe reuses the row while polar_subscription_id changes.
    """
    existing = Subscription.objects.filter(organization=organization).first()

    if existing is None or existing.polar_product_id != subscription.product_id:
        if not (plan_key := resolve_plan(subscription.product_id)):
            raise UnprocessableEventError(f"Unknown product id: {subscription.product_id}")

        snapshot = {
            "polar_product_id": subscription.product_id,
            "plan_key": plan_key,
            "amount": subscription.amount,
            "currency": subscription.currency,
        }
    else:
        snapshot = {}

    if existing is not None and existing.is_active and existing.polar_subscription_id != subscription.id:
        logger.warning(
            "Subscription ID changed for organization %s while active (%s -> %s): possible double checkout",
            organization.uuid,
            existing.polar_subscription_id,
            subscription.id,
        )

    Subscription.objects.update_or_create(
        organization=organization,
        defaults={
            "polar_customer_id": polar_customer_id,
            "polar_subscription_id": subscription.id,
            "status": subscription.status,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "current_period_end": subscription.current_period_end,
            **snapshot,
        },
    )


def sync_subscription_state(organization: Organization) -> None:
    """Best-effort one-time sync from customers.get_state_external. Never raises."""
    try:
        state = get_polar_client().customers.get_state_external(str(organization.uuid))
    except Exception:  # noqa: BLE001
        return

    for subscription in state.active_subscriptions:
        try:
            upsert_subscription(organization, subscription, polar_customer_id=state.id)
        except UnprocessableEventError:
            continue
