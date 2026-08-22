from django.db import models

from apps.billing.plans import BILLING_PLANS
from apps.billing.plans import Plan
from apps.billing.plans import PlanKey


class Subscription(models.Model):
    """The organization's current Polar subscription, snapshotted from webhook payloads."""

    class Status(models.TextChoices):
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"
        UNPAID = "unpaid", "Unpaid"
        PAUSED = "paused", "Paused"

    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.CASCADE, related_name="subscription"
    )

    polar_customer_id = models.CharField(max_length=36, unique=True)
    polar_subscription_id = models.CharField(max_length=36, unique=True)
    polar_product_id = models.CharField(max_length=36)

    plan_key = models.CharField(max_length=20, choices=PlanKey.choices)
    amount = models.PositiveIntegerField(help_text="Stored in the smallest unit of the local currency (e.g. cents).")
    currency = models.CharField(max_length=3)

    status = models.CharField(max_length=20, choices=Status.choices)
    cancel_at_period_end = models.BooleanField(default=False)
    current_period_end = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    organization_id: int

    def __str__(self) -> str:
        return f"{self.organization} - {self.plan_key} ({self.status})"

    @property
    def is_active(self) -> bool:
        return self.status in (
            self.Status.TRIALING,
            self.Status.ACTIVE,
            self.Status.PAST_DUE,
        )

    @property
    def plan(self) -> Plan:
        return BILLING_PLANS[PlanKey(self.plan_key)]


class WebhookEvent(models.Model):
    """Idempotency + audit record for Polar webhook deliveries."""

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        PROCESSED = "processed", "Processed"
        ERROR = "error", "Error"

    polar_event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=50)
    payload = models.JSONField()
    status = models.CharField(max_length=10, choices=Status.choices)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.event_type} ({self.status})"
