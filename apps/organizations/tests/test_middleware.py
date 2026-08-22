from http import HTTPStatus
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory
from django.test import TestCase

from apps.accounts.models import User
from apps.organizations.middleware import active_organization_integrity_middleware
from apps.organizations.models import Organization
from apps.organizations.models import OrganizationMembership


def run_middleware(user: User | AnonymousUser) -> HttpResponse:
    request = RequestFactory().get("/")
    request.user = user
    middleware = active_organization_integrity_middleware(lambda _request: HttpResponse())
    return middleware(request)


class ActiveOrganizationIntegrityMiddlewareTests(TestCase):
    """Tests for active_organization_integrity_middleware."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        cls.other_organization = Organization.objects.create(name="Globex")

    def test_anonymous_user_passes_through(self) -> None:
        response = run_middleware(AnonymousUser())

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_valid_active_organization_is_kept_without_save(self) -> None:
        user = User.objects.create_user("owner@example.com", "test-password")
        OrganizationMembership.objects.create(
            user=user, organization=self.organization, role=OrganizationMembership.Role.OWNER
        )
        user.active_organization = self.organization
        user.save(update_fields=["active_organization"])

        with patch.object(user, "save") as mocked_save:
            response = run_middleware(user)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        mocked_save.assert_not_called()
        self.assertEqual(user.active_organization_id, self.organization.pk)

    def test_stale_active_organization_falls_back_to_first_membership(self) -> None:
        user = User.objects.create_user("member@example.com", "test-password")
        OrganizationMembership.objects.create(user=user, organization=self.organization)
        user.active_organization = self.other_organization
        user.save(update_fields=["active_organization"])

        run_middleware(user)

        user.refresh_from_db()
        self.assertEqual(user.active_organization_id, self.organization.pk)

    def test_stale_active_organization_without_memberships_becomes_none(self) -> None:
        user = User.objects.create_user("lost@example.com", "test-password")
        user.active_organization = self.organization
        user.save(update_fields=["active_organization"])

        run_middleware(user)

        user.refresh_from_db()
        self.assertIsNone(user.active_organization_id)

    def test_missing_active_organization_is_set_from_membership(self) -> None:
        user = User.objects.create_user("new@example.com", "test-password")
        OrganizationMembership.objects.create(user=user, organization=self.organization)

        run_middleware(user)

        user.refresh_from_db()
        self.assertEqual(user.active_organization_id, self.organization.pk)
