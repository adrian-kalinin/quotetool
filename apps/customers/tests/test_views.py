from http import HTTPStatus

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.billing.models import Subscription
from apps.billing.plans import PlanKey
from apps.customers.models import Address
from apps.customers.models import Customer
from apps.customers.tests.helpers import create_address
from apps.customers.tests.helpers import create_customer
from apps.customers.tests.helpers import customer_form_data
from apps.organizations.models import Organization
from apps.organizations.models import OrganizationMembership


class CustomerViewTestCase(TestCase):
    """Base setup: an organization with an active subscription and a member, plus a second organization."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        cls.other_organization = Organization.objects.create(name="Other Inc.")
        cls.user = cls.create_user(cls.organization, "owner@example.com")

    @classmethod
    def create_user(cls, organization: Organization, email: str) -> User:
        Subscription.objects.create(
            organization=organization,
            polar_customer_id="cust-1",
            polar_subscription_id="sub-1",
            polar_product_id="test-starter-id",
            plan_key=PlanKey.STARTER,
            amount=2900,
            currency="usd",
            status=Subscription.Status.ACTIVE,
        )
        user = User.objects.create_user(email, "test-password")
        user.active_organization = organization
        user.save(update_fields=["active_organization"])
        OrganizationMembership.objects.create(user=user, organization=organization)
        return user

    def setUp(self) -> None:
        self.client.force_login(self.user)


class CustomerListViewTests(CustomerViewTestCase):
    """Tests for CustomerListView."""

    def test_anonymous_user_is_redirected_to_login(self) -> None:
        self.client.logout()

        response = self.client.get(reverse("customers:customer-list"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn(reverse("account_login"), response["Location"])

    def test_only_lists_customers_of_active_organization(self) -> None:
        own_customer = create_customer(self.organization, company_name="Own Ltd.", email="own@example.test")
        create_customer(self.other_organization, company_name="Other Ltd.", email="other@example.test")

        response = self.client.get(reverse("customers:customer-list"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(list(response.context["customers"]), [own_customer])

    def test_search_filters_by_company_name(self) -> None:
        acme = create_customer(self.organization, company_name="Acme GmbH", email="acme@example.test")
        create_customer(self.organization, company_name="Beta Ltd.", email="beta@example.test")

        response = self.client.get(reverse("customers:customer-list"), {"q": "acme"})

        self.assertEqual(list(response.context["customers"]), [acme])

    def test_search_does_not_leak_other_organizations(self) -> None:
        create_customer(self.other_organization, company_name="Acme Other", email="acme@example.test")

        response = self.client.get(reverse("customers:customer-list"), {"q": "acme"})

        self.assertEqual(list(response.context["customers"]), [])

    def test_htmx_request_targeting_results_returns_partial(self) -> None:
        response = self.client.get(
            reverse("customers:customer-list"),
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="customer-list-container",
        )

        self.assertTemplateUsed(response, "customers/partials/customer_list_results.html")

    def test_boosted_htmx_request_returns_full_page(self) -> None:
        response = self.client.get(reverse("customers:customer-list"), HTTP_HX_REQUEST="true", HTTP_HX_BOOSTED="true")

        self.assertTemplateUsed(response, "customers/customer_list.html")

    def test_paginates_customers(self) -> None:
        for index in range(25):
            create_customer(
                self.organization, company_name=f"Company {index:02d}", email=f"company{index}@example.test"
            )

        response = self.client.get(reverse("customers:customer-list"))

        self.assertEqual(len(response.context["customers"]), 10)
        self.assertContains(response, "?page=2")

        second_page = self.client.get(reverse("customers:customer-list"), {"page": 2})
        self.assertEqual(len(second_page.context["customers"]), 10)

        third_page = self.client.get(reverse("customers:customer-list"), {"page": 3})
        self.assertEqual(len(third_page.context["customers"]), 5)


class CustomerDetailViewTests(CustomerViewTestCase):
    """Tests for CustomerDetailView."""

    def test_renders_customer_of_active_organization(self) -> None:
        customer = create_customer(
            self.organization,
            type=Customer.Type.PRIVATE,
            company_name="",
            first_name="John",
            last_name="Doe",
            email="john@example.test",
        )

        response = self.client.get(reverse("customers:customer-detail", kwargs={"pk": customer.pk}))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "John Doe")

    def test_customer_of_another_organization_is_not_found(self) -> None:
        customer = create_customer(self.other_organization, company_name="Other Ltd.", email="other@example.test")

        response = self.client.get(reverse("customers:customer-detail", kwargs={"pk": customer.pk}))

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)


class CustomerCreateViewTests(CustomerViewTestCase):
    """Tests for CustomerCreateView."""

    def test_renders_customer_type_toggle(self) -> None:
        response = self.client.get(reverse("customers:customer-create"))

        self.assertContains(response, "btn-check")
        self.assertContains(response, 'value="corporate"')
        self.assertContains(response, 'value="private"')

    def test_country_field_renders_datalist_suggestions(self) -> None:
        response = self.client.get(reverse("customers:customer-create"))

        self.assertContains(response, 'list="address_country-datalist"')
        self.assertContains(response, 'id="address_country-datalist"')
        self.assertContains(response, '<option value="Germany">')
        self.assertNotContains(response, 'value="European Union"')

    def test_prefills_country_from_most_recent_customer(self) -> None:
        create_customer(self.organization, billing_address=create_address(self.organization, country="France"))

        response = self.client.get(reverse("customers:customer-create"))

        self.assertEqual(response.context["form"]["address_country"].value(), "France")

    def test_does_not_prefill_country_from_another_organization(self) -> None:
        create_customer(
            self.other_organization, billing_address=create_address(self.other_organization, country="Italy")
        )

        response = self.client.get(reverse("customers:customer-create"))

        self.assertIsNone(response.context["form"]["address_country"].value())

    def test_creates_corporate_customer_with_billing_address(self) -> None:
        response = self.client.post(
            reverse("customers:customer-create"),
            customer_form_data(
                phone="+49 30 123456",
                notes="Preferred customer.",
                address_line2="Suite 4",
                address_region="Berlin",
            ),
        )

        customer = Customer.objects.get()
        self.assertRedirects(response, reverse("customers:customer-detail", kwargs={"pk": customer.pk}))
        self.assertEqual(customer.organization, self.organization)
        self.assertEqual(customer.created_by, self.user)
        self.assertEqual(customer.updated_by, self.user)
        self.assertEqual(customer.phone.as_e164, "+4930123456")
        self.assertEqual(customer.billing_address.line1, "1 Main St")
        self.assertEqual(customer.billing_address.organization, self.organization)

    def test_rejects_invalid_phone_number(self) -> None:
        response = self.client.post(reverse("customers:customer-create"), customer_form_data(phone="not-a-phone"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("phone", response.context["form"].errors)
        self.assertFalse(Customer.objects.exists())

    def test_rejects_national_phone_number_without_country_code(self) -> None:
        response = self.client.post(reverse("customers:customer-create"), customer_form_data(phone="030 123456"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("phone", response.context["form"].errors)
        self.assertFalse(Customer.objects.exists())

    def test_requires_billing_address(self) -> None:
        response = self.client.post(
            reverse("customers:customer-create"),
            customer_form_data(
                type=Customer.Type.PRIVATE,
                first_name="John",
                last_name="Doe",
                email="john@example.test",
                address_line1="",
                address_city="",
                address_postal_code="",
                address_country="",
            ),
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)

        for field in ("address_line1", "address_city", "address_postal_code", "address_country"):
            self.assertIn(field, response.context["form"].errors)

        self.assertFalse(Customer.objects.exists())
        self.assertFalse(Address.objects.exists())

    def test_corporate_customer_requires_company_name(self) -> None:
        response = self.client.post(reverse("customers:customer-create"), customer_form_data(company_name=""))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("company_name", response.context["form"].errors)
        self.assertFalse(Customer.objects.exists())

    def test_private_customer_requires_first_and_last_name(self) -> None:
        response = self.client.post(
            reverse("customers:customer-create"),
            customer_form_data(type=Customer.Type.PRIVATE, first_name="", last_name=""),
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("first_name", response.context["form"].errors)
        self.assertIn("last_name", response.context["form"].errors)


class CustomerUpdateViewTests(CustomerViewTestCase):
    """Tests for CustomerUpdateView."""

    def test_renders_prefilled_billing_address(self) -> None:
        address = create_address(self.organization, line1="Old St 1")
        customer = create_customer(self.organization, billing_address=address)

        response = self.client.get(reverse("customers:customer-update", kwargs={"pk": customer.pk}))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, 'value="Old St 1"')
        self.assertContains(response, 'value="Acme GmbH"')

    def test_updates_customer_and_billing_address_in_place(self) -> None:
        address = create_address(self.organization, line1="Old St 1")
        customer = create_customer(self.organization, billing_address=address)

        response = self.client.post(
            reverse("customers:customer-update", kwargs={"pk": customer.pk}),
            customer_form_data(
                company_name="Acme GmbH (updated)",
                email="new@acme.test",
                address_line1="New St 2",
                address_city="Munich",
                address_postal_code="80331",
            ),
        )

        self.assertRedirects(response, reverse("customers:customer-detail", kwargs={"pk": customer.pk}))

        customer.refresh_from_db()
        self.assertEqual(customer.company_name, "Acme GmbH (updated)")
        self.assertEqual(customer.updated_by, self.user)
        self.assertEqual(Address.objects.count(), 1)
        self.assertEqual(customer.billing_address.pk, address.pk)
        self.assertEqual(customer.billing_address.line1, "New St 2")
        self.assertEqual(customer.billing_address.city, "Munich")

    def test_requires_billing_address(self) -> None:
        customer = create_customer(self.organization)
        address_id = customer.billing_address_id

        response = self.client.post(
            reverse("customers:customer-update", kwargs={"pk": customer.pk}),
            customer_form_data(address_line1="", address_city="", address_postal_code="", address_country=""),
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("address_line1", response.context["form"].errors)

        customer.refresh_from_db()
        self.assertEqual(customer.billing_address_id, address_id)

    def test_customer_of_another_organization_is_not_found(self) -> None:
        customer = create_customer(self.other_organization, company_name="Other Ltd.", email="other@example.test")

        response = self.client.get(reverse("customers:customer-update", kwargs={"pk": customer.pk}))

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
