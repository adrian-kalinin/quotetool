from django import forms
from django.utils.translation import gettext_lazy as _

from apps.customers.models import Address
from apps.customers.models import Customer
from apps.organizations.models import Organization


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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        if self.instance.pk is None:
            self.fields["type"].initial = Customer.Type.CORPORATE

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
