import json

from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.fields import SafeString

from apps.billing.models import Subscription
from apps.billing.models import WebhookEvent


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = (
        "organization",
        "plan_key",
        "status",
        "formatted_amount",
        "current_period_end",
    )
    list_filter = ("status", "plan_key")
    search_fields = ("organization__name", "polar_customer_id", "polar_subscription_id")

    fieldsets = (
        ("", {"fields": ("organization",)}),
        ("Subscription", {"fields": ("plan_key", "formatted_amount", "status")}),
        ("Polar", {"fields": ("polar_customer_id", "polar_subscription_id", "polar_product_id")}),
        ("Period", {"fields": ("current_period_end", "cancel_at_period_end")}),
        ("Dates", {"fields": ("updated_at", "created_at")}),
    )

    def has_add_permission(self, _: HttpRequest) -> bool:
        return False

    def has_change_permission(self, _: HttpRequest, __: Subscription | None = None) -> bool:
        return False

    def has_delete_permission(self, _: HttpRequest, __: Subscription | None = None) -> bool:
        return False

    @admin.display(description="Amount")
    def formatted_amount(self, obj: Subscription) -> str:
        return f"{obj.amount / 100:.2f} {obj.currency}"


@admin.register(WebhookEvent)
class WebhookEventAdmin(ModelAdmin):
    list_display = ("polar_event_id", "event_type", "status", "created_at")
    list_filter = ("status", "event_type")

    fieldsets = (
        ("", {"fields": ("polar_event_id", "event_type", "status", "error")}),
        ("Payload", {"fields": ("formatted_payload",)}),
        ("Dates", {"fields": ("created_at",)}),
    )

    def has_add_permission(self, _: HttpRequest) -> bool:
        return False

    def has_change_permission(self, _: HttpRequest, __: WebhookEvent | None = None) -> bool:
        return False

    def has_delete_permission(self, _: HttpRequest, __: WebhookEvent | None = None) -> bool:
        return False

    @admin.display(description="Data")
    def formatted_payload(self, obj: WebhookEvent) -> SafeString | None:
        return format_html(
            "<pre>{}</pre>",
            json.dumps(obj.payload, indent=2, ensure_ascii=False),
        )
