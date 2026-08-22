from http import HTTPStatus

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseBase
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.views import View

from apps.accounts.models import User
from apps.organizations.mixins import OrganizationAccessMixin
from apps.organizations.models import Organization
from apps.organizations.models import OrganizationMembership


class AnyRoleView(OrganizationAccessMixin, View):
    requires_subscription = False

    def get(self, _request: HttpRequest) -> HttpResponse:
        return HttpResponse("ok")


class OwnerOnlyView(OrganizationAccessMixin, View):
    allowed_roles = (OrganizationMembership.Role.OWNER,)
    requires_subscription = False

    def get(self, _request: HttpRequest) -> HttpResponse:
        return HttpResponse("ok")


class OrganizationAccessMixinTests(TestCase):
    """Tests for OrganizationAccessMixin."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")

    def setUp(self) -> None:
        self.factory = RequestFactory()

    def create_member(self, role: str) -> User:
        user = User.objects.create_user(f"{role}@example.com", "test-password")
        OrganizationMembership.objects.create(user=user, organization=self.organization, role=role)
        user.active_organization = self.organization
        user.save(update_fields=["active_organization"])
        return user

    def dispatch(self, view_class: type[View], user: User | AnonymousUser) -> HttpResponseBase:
        request = self.factory.get("/")
        request.user = user
        return view_class.as_view()(request)

    def test_anonymous_user_is_redirected_to_login(self) -> None:
        response = self.dispatch(AnyRoleView, AnonymousUser())

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn(reverse("account_login"), response["Location"])

    def test_user_without_active_organization_is_sent_to_onboarding(self) -> None:
        user = User.objects.create_user("fresh@example.com", "test-password")

        response = self.dispatch(AnyRoleView, user)

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:onboarding"))

    def test_user_with_active_organization_passes_without_role_check(self) -> None:
        user = self.create_member(OrganizationMembership.Role.MEMBER)

        response = self.dispatch(AnyRoleView, user)

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_allowed_role_passes(self) -> None:
        user = self.create_member(OrganizationMembership.Role.OWNER)

        response = self.dispatch(OwnerOnlyView, user)

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_disallowed_role_raises_permission_denied(self) -> None:
        user = self.create_member(OrganizationMembership.Role.ADMIN)

        with self.assertRaises(PermissionDenied):
            self.dispatch(OwnerOnlyView, user)

    def test_missing_membership_raises_permission_denied(self) -> None:
        user = User.objects.create_user("stale@example.com", "test-password")
        user.active_organization = self.organization
        user.save(update_fields=["active_organization"])

        with self.assertRaises(PermissionDenied):
            self.dispatch(OwnerOnlyView, user)
