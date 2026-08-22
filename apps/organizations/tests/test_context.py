from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
from django.test import RequestFactory
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.context import organizations
from apps.organizations.models import Organization
from apps.organizations.models import OrganizationInvitation
from apps.organizations.models import OrganizationMembership


def make_request(user: User | AnonymousUser) -> HttpRequest:
    request = RequestFactory().get("/")
    request.user = user
    return request


def create_invitation(
    organization: Organization,
    email: str,
    invited_by: User,
    *,
    expires_in_days: int = 7,
) -> OrganizationInvitation:
    return OrganizationInvitation.objects.create(
        organization=organization,
        email=email,
        invited_by=invited_by,
        expires_at=timezone.now() + timedelta(days=expires_in_days),
    )


class OrganizationsContextProcessorTests(TestCase):
    """Tests for the organizations context processor."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        cls.other_organization = Organization.objects.create(name="Globex")
        cls.user = User.objects.create_user("owner@example.com", "test-password")
        cls.user.active_organization = cls.other_organization
        cls.user.save(update_fields=["active_organization"])
        OrganizationMembership.objects.create(
            user=cls.user, organization=cls.organization, role=OrganizationMembership.Role.OWNER
        )
        OrganizationMembership.objects.create(
            user=cls.user, organization=cls.other_organization, role=OrganizationMembership.Role.MEMBER
        )
        cls.inviter = User.objects.create_user("inviter@example.com", "test-password")

    def test_anonymous_user_gets_empty_context(self) -> None:
        self.assertEqual(organizations(make_request(AnonymousUser())), {})

    def test_active_organization_comes_from_the_user(self) -> None:
        context = organizations(make_request(self.user))

        self.assertEqual(context["active_organization"], self.other_organization)

    def test_available_organizations_are_ordered_by_name(self) -> None:
        context = organizations(make_request(self.user))

        self.assertEqual(context["available_organizations"], [self.organization, self.other_organization])

    def test_pending_invitations_count_covers_only_actionable_invitations(self) -> None:
        create_invitation(self.organization, "Owner@Example.com", self.inviter)
        create_invitation(self.other_organization, self.user.email, self.inviter, expires_in_days=-1)
        create_invitation(self.organization, "someone-else@example.com", self.inviter)

        context = organizations(make_request(self.user))

        self.assertEqual(context["pending_invitations_count"], 1)

    def test_user_without_memberships_gets_empty_context_values(self) -> None:
        user = User.objects.create_user("fresh@example.com", "test-password")

        context = organizations(make_request(user))

        self.assertIsNone(context["active_organization"])
        self.assertEqual(context["available_organizations"], [])
        self.assertEqual(context["pending_invitations_count"], 0)
