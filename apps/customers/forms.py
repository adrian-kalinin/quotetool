from typing import Any

from babel import Locale
from django import forms
from django.conf import settings
from django.forms.renderers import BaseRenderer
from django.utils.html import format_html
from django.utils.html import format_html_join
from django.utils.safestring import SafeString
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from apps.customers.models import Address
from apps.customers.models import Customer
from apps.organizations.models import Organization

_NON_COUNTRY_TERRITORIES = frozenset({"EU", "EZ", "QO", "UN", "ZZ"})


def country_names() -> tuple[str, ...]:
    """Return country names in the active language."""
    language = (get_language() or settings.LANGUAGE_CODE).replace("-", "_")
    territories = Locale.parse(language).territories

    return tuple(
        sorted(name for code, name in territories.items() if code.isalpha() and code not in _NON_COUNTRY_TERRITORIES)
    )


class CountryInput(forms.TextInput):
    """Text input that suggests country names."""

    def render(
        self, name: str, value: object, attrs: dict[str, Any] | None = None, renderer: BaseRenderer | None = None
    ) -> SafeString:
        datalist_id = f"{name}-datalist"
        input_html = super().render(name, value, {**(attrs or {}), "list": datalist_id}, renderer)
        options_html = format_html_join("", '<option value="{}"></option>', ((country,) for country in country_names()))

        return format_html('{}<datalist id="{}">{}</datalist>', input_html, datalist_id, options_html)


class CustomerForm(forms.ModelForm):
    """Create or update a customer together with an owned billing address."""

    address_line1 = forms.CharField(label=_("Address line 1"), max_length=255)
    address_line2 = forms.CharField(label=_("Address line 2"), max_length=255, required=False)
    address_city = forms.CharField(label=_("City"), max_length=100)
    address_region = forms.CharField(label=_("State / region"), max_length=100, required=False)
    address_postal_code = forms.CharField(label=_("Postal code"), max_length=20)
    address_country = forms.CharField(label=_("Country"), max_length=100)

    class Meta:
        model = Customer
        fields = ("type", "company_name", "first_name", "last_name", "email", "phone", "notes")

    def __init__(self, *args, organization: Organization | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.fields["address_country"].widget = CountryInput()

        if self.instance.pk is None:
            self.fields["type"].initial = Customer.Type.CORPORATE
            self._prefill_country(organization)

        self.fields["company_name"].widget.attrs["placeholder"] = _("Acme Inc.")
        self.fields["first_name"].widget.attrs["placeholder"] = _("John")
        self.fields["last_name"].widget.attrs["placeholder"] = _("Doe")
        self.fields["email"].widget.attrs["placeholder"] = _("john.doe@example.com")
        self.fields["phone"].widget.attrs["placeholder"] = _("+49 30 123456")
        self.fields["address_line1"].widget.attrs["placeholder"] = _("1 Main St")
        self.fields["address_line2"].widget.attrs["placeholder"] = _("Suite 4")
        self.fields["address_city"].widget.attrs["placeholder"] = _("Berlin")
        self.fields["address_region"].widget.attrs["placeholder"] = _("Berlin")
        self.fields["address_postal_code"].widget.attrs["placeholder"] = _("10115")
        self.fields["address_country"].widget.attrs["placeholder"] = _("Germany")

        if self.instance.pk and self.instance.billing_address_id:
            self.initial.update(
                {
                    "address_line1": self.instance.billing_address.line1,
                    "address_line2": self.instance.billing_address.line2,
                    "address_city": self.instance.billing_address.city,
                    "address_region": self.instance.billing_address.region,
                    "address_postal_code": self.instance.billing_address.postal_code,
                    "address_country": self.instance.billing_address.country,
                }
            )

    def _prefill_country(self, organization: Organization | None) -> None:
        """Prefill the billing country from the organization's most recently added customer."""
        if organization is None:
            return

        latest = (
            Customer.objects.filter(organization=organization)
            .select_related("billing_address")
            .order_by("-created_at")
            .first()
        )

        if latest is not None:
            self.fields["address_country"].initial = latest.billing_address.country

    def clean(self) -> dict[str, object]:
        cleaned = super().clean() or {}

        self._validate_type(cleaned)

        return cleaned

    def save(self, commit: bool = True) -> Customer:  # noqa: FBT001, FBT002
        customer = super().save(commit=False)
        customer.billing_address = self._save_billing_address(customer.organization)

        if commit:
            customer.save()

        return customer

    def _validate_type(self, cleaned: dict[str, object]) -> None:
        customer_type = cleaned.get("type")

        if customer_type == Customer.Type.CORPORATE and not cleaned.get("company_name"):
            self.add_error("company_name", _("Required for corporate customers."))

        if customer_type == Customer.Type.PRIVATE:
            if not cleaned.get("first_name"):
                self.add_error("first_name", _("Required for private customers."))
            if not cleaned.get("last_name"):
                self.add_error("last_name", _("Required for private customers."))

    def _save_billing_address(self, organization: Organization) -> Address:
        address = self.instance.billing_address if self.instance.pk else None

        if address is None:
            address = Address(organization=organization)

        address.line1 = self.cleaned_data["address_line1"]
        address.line2 = self.cleaned_data.get("address_line2", "")
        address.city = self.cleaned_data["address_city"]
        address.region = self.cleaned_data.get("address_region", "")
        address.postal_code = self.cleaned_data["address_postal_code"]
        address.country = self.cleaned_data["address_country"]
        address.save()

        return address
