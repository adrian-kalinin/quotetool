from django.contrib import admin
from django.db.models import Count
from django.db.models import QuerySet
from django.http import HttpRequest
from unfold.admin import ModelAdmin

from apps.organizations.models import Organization
from apps.organizations.models import OrganizationInvitation


@admin.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display = ("name", "uuid", "created_at")
    search_fields = ("name", "uuid")
    ordering = ("-created_at",)

    fieldsets = (
        (None, {"fields": ("name", "uuid", "users_count")}),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )
    readonly_fields = ("uuid", "users_count", "created_at", "updated_at")

    def get_queryset(self, request: HttpRequest) -> QuerySet[Organization]:
        return super().get_queryset(request).annotate(users_count=Count("memberships"))

    def has_add_permission(self, _request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, _request: HttpRequest, _obj: Organization | None = None) -> bool:
        return False

    @admin.display(description="Users")
    def users_count(self, instance: Organization) -> int:
        return instance.users_count  # type: ignore[reportAttributeAccessIssue]


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(ModelAdmin):
    list_display = ("email", "organization", "status", "expires_at")
    list_filter = ("status",)
    search_fields = ("email", "organization__name")
    ordering = ("-created_at",)

    fieldsets = (
        (None, {"fields": ("organization", "email", "invited_by", "status")}),
        ("Dates", {"fields": ("created_at", "expires_at", "accepted_at")}),
    )
    readonly_fields = ("organization", "email", "invited_by", "created_at", "expires_at", "accepted_at")

    def has_add_permission(self, _request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, _request: HttpRequest, _obj: OrganizationInvitation | None = None) -> bool:
        return False
