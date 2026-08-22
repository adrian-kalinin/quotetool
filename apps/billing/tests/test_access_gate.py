from http import HTTPStatus
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseBase
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.views import View

from apps.accounts.models import User
from apps.billing.models import Subscription
from apps.billing.plans import PlanKey
from apps.billing.prices import PlanPrice
from apps.organizations.mixins import OrganizationAccessMixin
from apps.organizations.models import Organization
from apps.organizations.models import OrganizationMembership


class GatedView(OrganizationAccessMixin, View):
    def get(self, _request: HttpRequest) -> HttpResponse:
        return HttpResponse("ok")


class OptOutView(OrganizationAccessMixin, View):
    requires_subscription = False

    def get(self, _request: HttpRequest) -> HttpResponse:
        return HttpResponse("ok")


class SubscriptionAccessGateTests(TestCase):
    """Tests for the subscription access gate folded into OrganizationAccessMixin."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")

    def setUp(self) -> None:
        self.factory = RequestFactory()

    def create_member(self, email: str = "member@example.com") -> User:
        user = User.objects.create_user(email, "test-password")
        OrganizationMembership.objects.create(
            user=user, organization=self.organization, role=OrganizationMembership.Role.MEMBER
        )
        user.active_organization = self.organization
        user.save(update_fields=["active_organization"])
        return user

    def create_subscription(self, *, status: str) -> None:
        Subscription.objects.create(
            organization=self.organization,
            polar_customer_id="cust-1",
            polar_subscription_id="sub-1",
            polar_product_id="test-starter-id",
            plan_key=PlanKey.STARTER,
            amount=2900,
            currency="usd",
            status=status,
        )

    def dispatch(self, view_class: type[View], user: User | AnonymousUser) -> HttpResponseBase:
        request = self.factory.get("/")
        request.user = user
        return view_class.as_view()(request)

    def test_gated_view_redirects_without_subscription(self) -> None:
        user = self.create_member()

        response = self.dispatch(GatedView, user)

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("billing:settings-billing"))

    def test_opt_out_view_passes_without_subscription(self) -> None:
        user = self.create_member()

        response = self.dispatch(OptOutView, user)

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_gated_view_redirects_for_canceled_subscription(self) -> None:
        user = self.create_member()
        self.create_subscription(status=Subscription.Status.CANCELED)

        response = self.dispatch(GatedView, user)

        self.assertEqual(response["Location"], reverse("billing:settings-billing"))

    def test_gated_view_passes_with_active_subscription(self) -> None:
        user = self.create_member()
        self.create_subscription(status=Subscription.Status.ACTIVE)

        response = self.dispatch(GatedView, user)

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_gated_view_passes_with_trialing_subscription(self) -> None:
        user = self.create_member()
        self.create_subscription(status=Subscription.Status.TRIALING)

        response = self.dispatch(GatedView, user)

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_dashboard_is_gated_without_subscription(self) -> None:
        user = self.create_member()
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard:dashboard"))

        self.assertRedirects(response, reverse("billing:settings-billing"), fetch_redirect_response=False)

    def test_account_settings_are_reachable_without_subscription(self) -> None:
        user = self.create_member()
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:settings-account"))

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_billing_settings_are_reachable_without_subscription(self) -> None:
        user = self.create_member()
        self.client.force_login(user)

        with mock.patch("apps.billing.prices.get_plan_price", return_value=PlanPrice(2900, "usd")):
            response = self.client.get(reverse("billing:settings-billing"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
