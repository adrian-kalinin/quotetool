from django.contrib import admin
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.widgets import UnfoldAdminTextInputWidget

from apps.customers.forms import CustomerForm
from apps.customers.models import Customer


class CustomerAdminForm(CustomerForm):
    """Admin customer form that also exposes the owning organization."""

    class Meta(CustomerForm.Meta):
        fields = (*CustomerForm.Meta.fields, "organization")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        for name in CustomerForm.declared_fields:
            self.fields[name].widget = UnfoldAdminTextInputWidget()


@admin.register(Customer)
class CustomerAdmin(ModelAdmin):
    """Manage customers with their owned billing address edited inline."""

    form = CustomerAdminForm

    list_display = ("customer_name", "email", "billing_address", "organization", "created_at")
    search_fields = ("company_name", "first_name", "last_name", "email", "organization__name")
    ordering = ("-created_at",)
    autocomplete_fields = ("organization",)
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "organization",
                    "type",
                    "company_name",
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                    "notes",
                )
            },
        ),
        (
            _("Billing address"),
            {
                "fields": (
                    "address_line1",
                    "address_line2",
                    "address_city",
                    "address_region",
                    "address_postal_code",
                    "address_country",
                )
            },
        ),
        (_("Metadata"), {"fields": ("created_at", "updated_at", "created_by", "updated_by")}),
    )

    def get_readonly_fields(self, request: HttpRequest, obj: Customer | None = None) -> list[str] | tuple[str, ...]:
        readonly = super().get_readonly_fields(request, obj)

        if obj is not None:
            return (*readonly, "organization")

        return readonly

    @admin.display(description=_("Name"))
    def customer_name(self, obj: Customer) -> str:
        return obj.display_name
