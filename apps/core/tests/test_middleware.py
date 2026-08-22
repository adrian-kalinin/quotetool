from http import HTTPStatus
from unittest import mock
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.billing.prices import PlanPrice
from apps.organizations.models import Organization
from apps.organizations.models import OrganizationMembership


class HtmxOnlyMiddlewareTests(TestCase):
    """Non-htmx requests to htmx-only endpoints are redirected to the parent page."""

    def test_non_htmx_request_to_messages_endpoint_redirects(self) -> None:
        response = self.client.get(reverse("core:hx-messages"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("dashboard:dashboard"))

    def test_htmx_request_to_messages_endpoint_passes_through(self) -> None:
        response = self.client.get(reverse("core:hx-messages"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_regular_page_is_not_affected(self) -> None:
        with mock.patch("apps.billing.prices.get_plan_price", return_value=PlanPrice(2900, "usd")):
            response = self.client.get(reverse("pages:landing"))

        self.assertEqual(response.status_code, HTTPStatus.OK)


class HtmxMessagesMiddlewareTests(TestCase):
    """Queued messages add a fetch-messages client event header to the response."""

    def test_event_header_is_set_when_messages_are_queued(self) -> None:
        organization = Organization.objects.create(name="Acme Inc.")
        user = User.objects.create_user("owner@example.com", "test-password")
        OrganizationMembership.objects.create(
            user=user, organization=organization, role=OrganizationMembership.Role.OWNER
        )
        user.active_organization = organization
        user.save(update_fields=["active_organization"])
        self.client.force_login(user)

        # Switching to an organization the user is not a member of queues an error message.
        response = self.client.post(reverse("organizations:organization-switch", args=[uuid4()]))

        self.assertIn("fetch-messages", response.headers.get("HX-Trigger-After-Settle", ""))

    def test_no_event_header_without_messages(self) -> None:
        with mock.patch("apps.billing.prices.get_plan_price", return_value=PlanPrice(2900, "usd")):
            response = self.client.get(reverse("pages:landing"))

        self.assertNotIn("HX-Trigger-After-Settle", response.headers)
