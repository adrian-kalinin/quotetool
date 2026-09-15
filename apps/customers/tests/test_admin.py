from http import HTTPStatus

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.customers.models import Address
from apps.customers.models import Customer
from apps.organizations.models import Organization


class CustomerAdminTests(TestCase):
    """Tests for the customer admin, including the inline-owned billing address."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        cls.superuser = User.objects.create_superuser("admin@example.com", "test-password")

    def setUp(self) -> None:
        self.client.force_login(self.superuser)

    def create_customer(self, *, address: Address | None = None) -> Customer:
        return Customer.objects.create(
            organization=self.organization,
            type=Customer.Type.CORPORATE,
            company_name="Acme GmbH",
            email="billing@acme.test",
            billing_address=address,
        )

    def create_address(self) -> Address:
        return Address.objects.create(
            organization=self.organization,
            line1="Old St 1",
            city="Berlin",
            postal_code="10115",
            country="Germany",
        )

    def test_change_page_renders_editable_address_inputs(self) -> None:
        customer = self.create_customer(address=self.create_address())

        response = self.client.get(reverse("admin:customers_customer_change", kwargs={"object_id": customer.pk}))

        self.assertContains(response, 'name="address_line1"')
        self.assertContains(response, 'name="address_city"')
        self.assertContains(response, 'name="address_country"')

    def test_organization_is_editable_when_adding(self) -> None:
        response = self.client.get(reverse("admin:customers_customer_add"))

        self.assertContains(response, 'name="organization"')

    def test_organization_is_readonly_when_editing(self) -> None:
        customer = self.create_customer()

        response = self.client.get(reverse("admin:customers_customer_change", kwargs={"object_id": customer.pk}))

        self.assertNotContains(response, 'name="organization"')

    def test_change_keeps_organization_without_posting_it(self) -> None:
        customer = self.create_customer()

        response = self.client.post(
            reverse("admin:customers_customer_change", kwargs={"object_id": customer.pk}),
            {
                "type": Customer.Type.CORPORATE,
                "company_name": "Acme GmbH",
                "email": "billing@acme.test",
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.FOUND)

        customer.refresh_from_db()
        self.assertEqual(customer.organization, self.organization)

    def test_change_page_updates_billing_address(self) -> None:
        address = self.create_address()
        customer = self.create_customer(address=address)

        response = self.client.post(
            reverse("admin:customers_customer_change", kwargs={"object_id": customer.pk}),
            {
                "organization": self.organization.pk,
                "type": Customer.Type.CORPORATE,
                "company_name": "Acme GmbH",
                "email": "billing@acme.test",
                "address_line1": "New St 2",
                "address_city": "Munich",
                "address_postal_code": "80331",
                "address_country": "Germany",
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.FOUND)

        customer.refresh_from_db()
        self.assertEqual(customer.billing_address.pk, address.pk)
        self.assertEqual(customer.billing_address.line1, "New St 2")
        self.assertEqual(customer.billing_address.city, "Munich")

    def test_add_customer_creates_billing_address(self) -> None:
        response = self.client.post(
            reverse("admin:customers_customer_add"),
            {
                "organization": self.organization.pk,
                "type": Customer.Type.CORPORATE,
                "company_name": "Acme GmbH",
                "email": "billing@acme.test",
                "address_line1": "1 Main St",
                "address_city": "Berlin",
                "address_postal_code": "10115",
                "address_country": "Germany",
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.FOUND)

        customer = Customer.objects.get()
        self.assertIsNotNone(customer.billing_address)
        self.assertEqual(customer.billing_address.line1, "1 Main St")
        self.assertEqual(customer.billing_address.organization, self.organization)

    def test_edit_customer_clears_billing_address(self) -> None:
        address = self.create_address()
        customer = self.create_customer(address=address)

        response = self.client.post(
            reverse("admin:customers_customer_change", kwargs={"object_id": customer.pk}),
            {
                "organization": self.organization.pk,
                "type": Customer.Type.CORPORATE,
                "company_name": "Acme GmbH",
                "email": "billing@acme.test",
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.FOUND)

        customer.refresh_from_db()
        self.assertIsNone(customer.billing_address)
        self.assertFalse(Address.objects.filter(pk=address.pk).exists())

    def test_delete_customer_removes_billing_address(self) -> None:
        address = self.create_address()
        customer = self.create_customer(address=address)

        response = self.client.post(
            reverse("admin:customers_customer_delete", kwargs={"object_id": customer.pk}),
            {"post": "yes"},
        )

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertFalse(Customer.objects.filter(pk=customer.pk).exists())
        self.assertFalse(Address.objects.filter(pk=address.pk).exists())
