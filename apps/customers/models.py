from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.organizations.models import Organization


class Address(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="addresses")

    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    organization_id: int

    def __str__(self) -> str:
        return ", ".join(part for part in (self.line1, self.city, self.country) if part)


class Customer(models.Model):
    class Type(models.TextChoices):
        CORPORATE = "corporate", _("Corporate customer")
        PRIVATE = "private", _("Private person")

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="customers")
    type = models.CharField(max_length=10, choices=Type.choices)
    company_name = models.CharField(max_length=255, blank=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)
    billing_address = models.OneToOneField(Address, on_delete=models.PROTECT, related_name="billing_customer")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_customers"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="updated_customers"
    )

    organization_id: int
    billing_address_id: int

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        if self.type == self.Type.CORPORATE:
            return self.company_name
        return f"{self.first_name} {self.last_name}".strip()
