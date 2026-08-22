from allauth.account.models import EmailAddress
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.http import HttpRequest
from unfold.admin import ModelAdmin
from unfold.admin import TabularInline

from apps.accounts.models import User
from apps.organizations.models import OrganizationMembership

admin.site.unregister(Group)


class EmailAddressInline(TabularInline):
    model = EmailAddress
    hide_title = True
    fields = ("email", "verified", "primary")
    readonly_fields = ("email", "primary")

    def has_add_permission(self, _: HttpRequest, __: EmailAddress | None = None) -> bool:
        return False

    def has_delete_permission(self, _: HttpRequest, __: EmailAddress | None = None) -> bool:
        return False


class OrganizationMembershipInline(TabularInline):
    model = OrganizationMembership
    hide_title = True

    def has_change_permission(self, _: HttpRequest, __: OrganizationMembership | None = None) -> bool:
        return False

    def has_add_permission(self, _: HttpRequest, __: OrganizationMembership | None = None) -> bool:
        return False

    def has_delete_permission(self, _: HttpRequest, __: OrganizationMembership | None = None) -> bool:
        return False


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = ("email", "name", "last_login")
    search_fields = ("email", "name")
    ordering = ("-created_at",)

    fieldsets = (
        ("Personal Information", {"fields": ("email", "name", "active_organization", "password")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Dates", {"fields": ("last_login", "updated_at", "created_at")}),
    )
    readonly_fields = ("active_organization", "created_at", "updated_at", "last_login")

    inlines = [EmailAddressInline, OrganizationMembershipInline]

    def has_add_permission(self, _: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, _: HttpRequest, __: User | None = None) -> bool:
        return False
