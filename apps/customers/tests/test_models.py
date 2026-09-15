from django.test import TestCase

from apps.customers.models import Address
from apps.customers.models import Customer
from apps.organizations.models import Organization


class CustomerModelTests(TestCase):
    """Tests for the Customer model."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        cls.address = Address.objects.create(
            organization=cls.organization,
            line1="1 Main St",
            city="Berlin",
            postal_code="10115",
            country="Germany",
        )

    def test_display_name_for_corporate_customer(self) -> None:
        customer = Customer.objects.create(
            organization=self.organization,
            type=Customer.Type.CORPORATE,
            company_name="Acme Inc.",
            email="billing@acme.test",
            billing_address=self.address,
        )

        self.assertEqual(customer.display_name, "Acme Inc.")
        self.assertEqual(str(customer), "Acme Inc.")

    def test_display_name_for_private_customer(self) -> None:
        customer = Customer.objects.create(
            organization=self.organization,
            type=Customer.Type.PRIVATE,
            first_name="John",
            last_name="Doe",
            email="john@example.test",
            billing_address=self.address,
        )

        self.assertEqual(customer.display_name, "John Doe")


class AddressModelTests(TestCase):
    """Tests for the Address model."""

    def test_str_joins_line1_city_and_country(self) -> None:
        address = Address(
            organization=Organization.objects.create(name="Acme Inc."),
            line1="1 Main St",
            city="Berlin",
            postal_code="10115",
            country="Germany",
        )

        self.assertEqual(str(address), "1 Main St, Berlin, Germany")
