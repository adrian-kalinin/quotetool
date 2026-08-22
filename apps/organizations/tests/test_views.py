from datetime import timedelta
from http import HTTPStatus
from uuid import uuid4

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.models import Subscription
from apps.billing.plans import PlanKey
from apps.organizations.models import Organization
from apps.organizations.models import OrganizationInvitation
from apps.organizations.models import OrganizationMembership


def create_membership(organization: Organization, email: str, role: str) -> OrganizationMembership:
    user = User.objects.create_user(email, "test-password")
    user.active_organization = organization
    user.save(update_fields=["active_organization"])
    return OrganizationMembership.objects.create(user=user, organization=organization, role=role)


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


class OrganizationViewTestCase(TestCase):
    """Base setup: one organization with an owner, an admin, and a member."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        Subscription.objects.create(
            organization=cls.organization,
            polar_customer_id="cust-1",
            polar_subscription_id="sub-1",
            polar_product_id="prod-1",
            plan_key=PlanKey.STARTER,
            amount=2900,
            currency="usd",
            status=Subscription.Status.ACTIVE,
        )
        cls.owner_membership = create_membership(
            cls.organization, "owner@example.com", OrganizationMembership.Role.OWNER
        )
        cls.admin_membership = create_membership(
            cls.organization, "admin@example.com", OrganizationMembership.Role.ADMIN
        )
        cls.member_membership = create_membership(
            cls.organization, "member@example.com", OrganizationMembership.Role.MEMBER
        )
        cls.owner = cls.owner_membership.user
        cls.admin = cls.admin_membership.user
        cls.member = cls.member_membership.user


class OnboardingViewTests(TestCase):
    """Tests for OnboardingView."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        cls.inviter = create_membership(cls.organization, "owner@example.com", OrganizationMembership.Role.OWNER).user

    def test_anonymous_user_is_redirected_to_login(self) -> None:
        response = self.client.get(reverse("organizations:onboarding"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn(reverse("account_login"), response["Location"])

    def test_user_with_active_organization_goes_to_dashboard(self) -> None:
        membership = create_membership(self.organization, "member@example.com", OrganizationMembership.Role.MEMBER)
        self.client.force_login(membership.user)

        response = self.client.get(reverse("organizations:onboarding"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("dashboard:dashboard"))

    def test_user_with_pending_invitation_goes_to_invitations(self) -> None:
        user = User.objects.create_user("invitee@example.com", "test-password")
        create_invitation(self.organization, user.email, self.inviter)
        self.client.force_login(user)

        response = self.client.get(reverse("organizations:onboarding"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:invitations"))

    def test_user_with_expired_invitation_goes_to_create(self) -> None:
        user = User.objects.create_user("invitee@example.com", "test-password")
        create_invitation(self.organization, user.email, self.inviter, expires_in_days=-1)
        self.client.force_login(user)

        response = self.client.get(reverse("organizations:onboarding"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:organization-create"))

    def test_user_without_organization_or_invitation_goes_to_create(self) -> None:
        user = User.objects.create_user("fresh@example.com", "test-password")
        self.client.force_login(user)

        response = self.client.get(reverse("organizations:onboarding"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:organization-create"))


class OrganizationCreateViewTests(TestCase):
    """Tests for OrganizationCreateView."""

    def test_anonymous_user_is_redirected_to_login(self) -> None:
        response = self.client.get(reverse("organizations:organization-create"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn(reverse("account_login"), response["Location"])

    def test_get_renders_form(self) -> None:
        user = User.objects.create_user("fresh@example.com", "test-password")
        self.client.force_login(user)

        response = self.client.get(reverse("organizations:organization-create"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "organizations/create_organization.html")

    def test_post_creates_organization_with_owner_membership(self) -> None:
        user = User.objects.create_user("fresh@example.com", "test-password")
        self.client.force_login(user)

        response = self.client.post(reverse("organizations:organization-create"), {"name": "Acme Inc."})

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("dashboard:dashboard"))

        organization = Organization.objects.get(name="Acme Inc.")
        membership = OrganizationMembership.objects.get(user=user, organization=organization)
        self.assertEqual(membership.role, OrganizationMembership.Role.OWNER)

        user.refresh_from_db()
        self.assertEqual(user.active_organization, organization)

    def test_post_with_empty_name_shows_form_errors(self) -> None:
        user = User.objects.create_user("fresh@example.com", "test-password")
        self.client.force_login(user)

        response = self.client.post(reverse("organizations:organization-create"), {"name": ""})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("name", response.context["form"].errors)
        self.assertFalse(Organization.objects.exists())


class OrganizationSwitchViewTests(TestCase):
    """Tests for OrganizationSwitchView."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        cls.other_organization = Organization.objects.create(name="Globex")

    def test_member_switches_to_their_other_organization(self) -> None:
        membership = create_membership(self.organization, "multi@example.com", OrganizationMembership.Role.MEMBER)
        OrganizationMembership.objects.create(
            user=membership.user, organization=self.other_organization, role=OrganizationMembership.Role.MEMBER
        )
        self.client.force_login(membership.user)

        response = self.client.post(reverse("organizations:organization-switch", args=[self.other_organization.uuid]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("dashboard:dashboard"))

        membership.user.refresh_from_db()
        self.assertEqual(membership.user.active_organization, self.other_organization)

    def test_non_member_cannot_switch(self) -> None:
        membership = create_membership(self.organization, "solo@example.com", OrganizationMembership.Role.MEMBER)
        self.client.force_login(membership.user)

        response = self.client.post(reverse("organizations:organization-switch", args=[self.other_organization.uuid]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("dashboard:dashboard"))

        membership.user.refresh_from_db()
        self.assertEqual(membership.user.active_organization, self.organization)

    def test_get_is_not_allowed(self) -> None:
        membership = create_membership(self.organization, "solo@example.com", OrganizationMembership.Role.MEMBER)
        self.client.force_login(membership.user)

        response = self.client.get(reverse("organizations:organization-switch", args=[uuid4()]))

        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)


class OrganizationLeaveViewTests(OrganizationViewTestCase):
    """Tests for OrganizationLeaveView."""

    def test_member_can_leave_the_active_organization(self) -> None:
        self.client.force_login(self.member)

        response = self.client.post(reverse("organizations:organization-leave"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("dashboard:dashboard"))
        self.assertFalse(OrganizationMembership.objects.filter(pk=self.member_membership.pk).exists())

        self.member.refresh_from_db()
        self.assertIsNone(self.member.active_organization)

    def test_admin_can_leave_the_active_organization(self) -> None:
        self.client.force_login(self.admin)

        response = self.client.post(reverse("organizations:organization-leave"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertFalse(OrganizationMembership.objects.filter(pk=self.admin_membership.pk).exists())

        self.admin.refresh_from_db()
        self.assertIsNone(self.admin.active_organization)

    def test_owner_cannot_leave(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(reverse("organizations:organization-leave"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("dashboard:dashboard"))
        self.assertTrue(OrganizationMembership.objects.filter(pk=self.owner_membership.pk).exists())

        self.owner.refresh_from_db()
        self.assertEqual(self.owner.active_organization, self.organization)

    def test_user_without_an_organization_is_sent_to_onboarding(self) -> None:
        user = User.objects.create_user("fresh@example.com", "test-password")
        self.client.force_login(user)

        response = self.client.post(reverse("organizations:organization-leave"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:onboarding"))


class InvitationListViewTests(TestCase):
    """Tests for InvitationListView."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        cls.inviter = create_membership(cls.organization, "owner@example.com", OrganizationMembership.Role.OWNER).user

    def test_lists_pending_invitations_for_the_users_email(self) -> None:
        user = User.objects.create_user("invitee@example.com", "test-password")
        invitation = create_invitation(self.organization, user.email, self.inviter)
        self.client.force_login(user)

        response = self.client.get(reverse("organizations:invitations"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn(invitation, response.context["pending_invitations"])

    def test_expired_invitation_redirects_to_create(self) -> None:
        user = User.objects.create_user("invitee@example.com", "test-password")
        create_invitation(self.organization, user.email, self.inviter, expires_in_days=-1)
        self.client.force_login(user)

        response = self.client.get(reverse("organizations:invitations"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:organization-create"))

    def test_invitation_for_another_email_redirects_to_create(self) -> None:
        user = User.objects.create_user("invitee@example.com", "test-password")
        create_invitation(self.organization, "someone-else@example.com", self.inviter)
        self.client.force_login(user)

        response = self.client.get(reverse("organizations:invitations"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:organization-create"))

    def test_member_without_pending_invitations_goes_to_dashboard(self) -> None:
        membership = create_membership(self.organization, "member@example.com", OrganizationMembership.Role.MEMBER)
        self.client.force_login(membership.user)

        response = self.client.get(reverse("organizations:invitations"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("dashboard:dashboard"))


class InvitationAcceptViewTests(TestCase):
    """Tests for InvitationAcceptView."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        cls.inviter = create_membership(cls.organization, "owner@example.com", OrganizationMembership.Role.OWNER).user

    def test_accept_adds_user_to_the_organization(self) -> None:
        user = User.objects.create_user("invitee@example.com", "test-password")
        invitation = create_invitation(self.organization, user.email, self.inviter)
        self.client.force_login(user)

        response = self.client.post(reverse("organizations:invitation-accept", args=[invitation.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("dashboard:dashboard"))

        membership = OrganizationMembership.objects.get(user=user, organization=self.organization)
        self.assertEqual(membership.role, OrganizationMembership.Role.MEMBER)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.ACCEPTED)

        user.refresh_from_db()
        self.assertEqual(user.active_organization, self.organization)

    def test_accept_matches_email_case_insensitively(self) -> None:
        user = User.objects.create_user("invitee@example.com", "test-password")
        invitation = create_invitation(self.organization, "Invitee@Example.com", self.inviter)
        self.client.force_login(user)

        response = self.client.post(reverse("organizations:invitation-accept", args=[invitation.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertTrue(OrganizationMembership.objects.filter(user=user, organization=self.organization).exists())

    def test_invitation_for_another_email_cannot_be_accepted(self) -> None:
        user = User.objects.create_user("invitee@example.com", "test-password")
        invitation = create_invitation(self.organization, "someone-else@example.com", self.inviter)
        self.client.force_login(user)

        response = self.client.post(reverse("organizations:invitation-accept", args=[invitation.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:invitations"))

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.PENDING)
        self.assertFalse(OrganizationMembership.objects.filter(user=user, organization=self.organization).exists())

    def test_expired_invitation_cannot_be_accepted(self) -> None:
        user = User.objects.create_user("invitee@example.com", "test-password")
        invitation = create_invitation(self.organization, user.email, self.inviter, expires_in_days=-1)
        self.client.force_login(user)

        response = self.client.post(reverse("organizations:invitation-accept", args=[invitation.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:invitations"))

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.PENDING)

    def test_get_is_not_allowed(self) -> None:
        user = User.objects.create_user("invitee@example.com", "test-password")
        self.client.force_login(user)

        response = self.client.get(reverse("organizations:invitation-accept", args=[1]))

        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)


class InvitationDeclineViewTests(TestCase):
    """Tests for InvitationDeclineView."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        cls.inviter = create_membership(cls.organization, "owner@example.com", OrganizationMembership.Role.OWNER).user

    def test_decline_marks_invitation_declined(self) -> None:
        user = User.objects.create_user("invitee@example.com", "test-password")
        invitation = create_invitation(self.organization, user.email, self.inviter)
        self.client.force_login(user)

        response = self.client.post(reverse("organizations:invitation-decline", args=[invitation.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:invitations"))

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.DECLINED)

    def test_invitation_for_another_email_cannot_be_declined(self) -> None:
        user = User.objects.create_user("invitee@example.com", "test-password")
        invitation = create_invitation(self.organization, "someone-else@example.com", self.inviter)
        self.client.force_login(user)

        response = self.client.post(reverse("organizations:invitation-decline", args=[invitation.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:invitations"))

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.PENDING)


class SettingsOrganizationViewTests(OrganizationViewTestCase):
    """Tests for SettingsOrganizationView."""

    def test_manager_sees_invite_form_and_pending_invitations(self) -> None:
        invitation = create_invitation(self.organization, "new@example.com", self.owner)
        self.client.force_login(self.owner)

        response = self.client.get(reverse("organizations:settings-organization"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIsNotNone(response.context["invite_form"])
        self.assertIsNotNone(response.context["organization_form"])
        self.assertIn(invitation, response.context["pending_invitations"])

    def test_member_sees_neither_invite_form_nor_invitations(self) -> None:
        create_invitation(self.organization, "new@example.com", self.owner)
        self.client.force_login(self.member)

        response = self.client.get(reverse("organizations:settings-organization"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIsNone(response.context["invite_form"])
        self.assertIsNone(response.context["organization_form"])
        self.assertEqual(list(response.context["pending_invitations"]), [])

    def test_user_without_organization_is_sent_to_onboarding(self) -> None:
        user = User.objects.create_user("fresh@example.com", "test-password")
        self.client.force_login(user)

        response = self.client.get(reverse("organizations:settings-organization"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:onboarding"))

    def test_member_sees_leave_organization_form(self) -> None:
        self.client.force_login(self.member)

        response = self.client.get(reverse("organizations:settings-organization"))

        self.assertContains(response, reverse("organizations:organization-leave"))

    def test_owner_does_not_see_leave_organization_form(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.get(reverse("organizations:settings-organization"))

        self.assertNotContains(response, reverse("organizations:organization-leave"))

    def test_anonymous_user_is_redirected_to_login(self) -> None:
        response = self.client.get(reverse("organizations:settings-organization"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn(reverse("account_login"), response["Location"])


class OrganizationUpdateViewTests(OrganizationViewTestCase):
    """Tests for OrganizationUpdateView."""

    def test_owner_can_update_the_organization_name(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(reverse("organizations:settings-organization-details"), {"name": "Globex Inc."})

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:settings-organization"))

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, "Globex Inc.")

    def test_htmx_update_renders_details_partial(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("organizations:settings-organization-details"), {"name": "Globex Inc."}, HTTP_HX_REQUEST="true"
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "organizations/partials/settings_organization_details.html")

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, "Globex Inc.")

    def test_admin_can_update(self) -> None:
        self.client.force_login(self.admin)

        response = self.client.post(reverse("organizations:settings-organization-details"), {"name": "Globex Inc."})

        self.assertEqual(response.status_code, HTTPStatus.FOUND)

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, "Globex Inc.")

    def test_member_cannot_update(self) -> None:
        self.client.force_login(self.member)

        response = self.client.post(reverse("organizations:settings-organization-details"), {"name": "Globex Inc."})

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, "Acme Inc.")

    def test_empty_name_shows_form_errors(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(reverse("organizations:settings-organization-details"), {"name": ""})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("name", response.context["organization_form"].errors)

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, "Acme Inc.")


class MemberInviteViewTests(OrganizationViewTestCase):
    """Tests for MemberInviteView."""

    def test_owner_can_invite_a_new_email(self) -> None:
        self.client.force_login(self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("organizations:settings-member-invite"), {"email": "new@example.com"})

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:settings-organization"))

        invitation = OrganizationInvitation.objects.get(organization=self.organization, email="new@example.com")
        self.assertEqual(invitation.status, OrganizationInvitation.Status.PENDING)
        self.assertEqual(len(mail.outbox), 1)

    def test_htmx_invite_renders_invitations_partial(self) -> None:
        self.client.force_login(self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("organizations:settings-member-invite"), {"email": "new@example.com"}, HTTP_HX_REQUEST="true"
            )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "organizations/partials/settings_invitations.html")
        self.assertTrue(
            OrganizationInvitation.objects.filter(organization=self.organization, email="new@example.com").exists()
        )

    def test_admin_can_invite(self) -> None:
        self.client.force_login(self.admin)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("organizations:settings-member-invite"), {"email": "new@example.com"})

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertTrue(
            OrganizationInvitation.objects.filter(organization=self.organization, email="new@example.com").exists()
        )

    def test_member_cannot_invite(self) -> None:
        self.client.force_login(self.member)

        response = self.client.post(reverse("organizations:settings-member-invite"), {"email": "new@example.com"})

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertFalse(
            OrganizationInvitation.objects.filter(organization=self.organization, email="new@example.com").exists()
        )

    def test_inviting_an_existing_member_creates_no_invitation(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(reverse("organizations:settings-member-invite"), {"email": self.member.email})

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertFalse(
            OrganizationInvitation.objects.filter(organization=self.organization, email=self.member.email).exists()
        )

    def test_invalid_email_shows_form_errors(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(reverse("organizations:settings-member-invite"), {"email": "not-an-email"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("email", response.context["invite_form"].errors)
        self.assertFalse(OrganizationInvitation.objects.filter(organization=self.organization).exists())


class InvitationRevokeViewTests(OrganizationViewTestCase):
    """Tests for InvitationRevokeView in organization settings."""

    def test_owner_can_revoke_a_pending_invitation(self) -> None:
        invitation = create_invitation(self.organization, "new@example.com", self.owner)
        self.client.force_login(self.owner)

        response = self.client.post(reverse("organizations:settings-invitation-revoke", args=[invitation.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:settings-organization"))

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.REVOKED)

    def test_htmx_revoke_renders_invitations_partial(self) -> None:
        invitation = create_invitation(self.organization, "new@example.com", self.owner)
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("organizations:settings-invitation-revoke", args=[invitation.pk]), HTTP_HX_REQUEST="true"
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "organizations/partials/settings_invitations.html")

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.REVOKED)

    def test_revoking_a_non_pending_invitation_keeps_its_status(self) -> None:
        invitation = create_invitation(self.organization, "new@example.com", self.owner)
        invitation.status = OrganizationInvitation.Status.ACCEPTED
        invitation.save(update_fields=["status"])
        self.client.force_login(self.owner)

        response = self.client.post(reverse("organizations:settings-invitation-revoke", args=[invitation.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.ACCEPTED)

    def test_member_cannot_revoke(self) -> None:
        invitation = create_invitation(self.organization, "new@example.com", self.owner)
        self.client.force_login(self.member)

        response = self.client.post(reverse("organizations:settings-invitation-revoke", args=[invitation.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.PENDING)


class InvitationResendViewTests(OrganizationViewTestCase):
    """Tests for InvitationResendView in organization settings."""

    def test_owner_can_resend_a_pending_invitation(self) -> None:
        invitation = create_invitation(self.organization, "new@example.com", self.owner, expires_in_days=2)
        self.client.force_login(self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("organizations:settings-invitation-resend", args=[invitation.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:settings-organization"))

        invitation.refresh_from_db()
        self.assertGreaterEqual(invitation.expires_at, timezone.now() + timedelta(days=7, minutes=-1))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new@example.com"])

    def test_resending_a_non_pending_invitation_sends_no_email(self) -> None:
        invitation = create_invitation(self.organization, "new@example.com", self.owner, expires_in_days=2)
        invitation.status = OrganizationInvitation.Status.REVOKED
        invitation.save(update_fields=["status"])
        self.client.force_login(self.owner)

        response = self.client.post(reverse("organizations:settings-invitation-resend", args=[invitation.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)

        invitation.refresh_from_db()
        self.assertLess(invitation.expires_at, timezone.now() + timedelta(days=3))
        self.assertEqual(len(mail.outbox), 0)

    def test_member_cannot_resend(self) -> None:
        invitation = create_invitation(self.organization, "new@example.com", self.owner)
        self.client.force_login(self.member)

        response = self.client.post(reverse("organizations:settings-invitation-resend", args=[invitation.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)


class MemberRoleUpdateViewTests(OrganizationViewTestCase):
    """Tests for MemberRoleUpdateView."""

    def test_owner_can_promote_member_to_admin(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("organizations:settings-member-role", args=[self.member_membership.pk]),
            {"role": OrganizationMembership.Role.ADMIN},
        )

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:settings-organization"))

        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, OrganizationMembership.Role.ADMIN)

    def test_htmx_role_update_renders_members_partial(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("organizations:settings-member-role", args=[self.member_membership.pk]),
            {"role": OrganizationMembership.Role.ADMIN},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "organizations/partials/settings_members.html")

    def test_admin_can_change_member_role(self) -> None:
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("organizations:settings-member-role", args=[self.member_membership.pk]),
            {"role": OrganizationMembership.Role.ADMIN},
        )

        self.assertEqual(response.status_code, HTTPStatus.FOUND)

        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, OrganizationMembership.Role.ADMIN)

    def test_owner_role_cannot_be_changed(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("organizations:settings-member-role", args=[self.owner_membership.pk]),
            {"role": OrganizationMembership.Role.MEMBER},
        )

        self.assertEqual(response.status_code, HTTPStatus.FOUND)

        self.owner_membership.refresh_from_db()
        self.assertEqual(self.owner_membership.role, OrganizationMembership.Role.OWNER)

    def test_invalid_role_is_rejected(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("organizations:settings-member-role", args=[self.member_membership.pk]),
            {"role": OrganizationMembership.Role.OWNER},
        )

        self.assertEqual(response.status_code, HTTPStatus.FOUND)

        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, OrganizationMembership.Role.MEMBER)

    def test_membership_from_another_organization_is_not_found(self) -> None:
        other_organization = Organization.objects.create(name="Globex")
        other_membership = create_membership(
            other_organization, "member@globex.com", OrganizationMembership.Role.MEMBER
        )
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("organizations:settings-member-role", args=[other_membership.pk]),
            {"role": OrganizationMembership.Role.ADMIN},
        )

        self.assertEqual(response.status_code, HTTPStatus.FOUND)

        other_membership.refresh_from_db()
        self.assertEqual(other_membership.role, OrganizationMembership.Role.MEMBER)


class MemberRemoveViewTests(OrganizationViewTestCase):
    """Tests for MemberRemoveView."""

    def test_owner_can_remove_a_member(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(reverse("organizations:settings-member-remove", args=[self.member_membership.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:settings-organization"))
        self.assertFalse(OrganizationMembership.objects.filter(pk=self.member_membership.pk).exists())

    def test_admin_can_remove_a_member(self) -> None:
        self.client.force_login(self.admin)

        response = self.client.post(reverse("organizations:settings-member-remove", args=[self.member_membership.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertFalse(OrganizationMembership.objects.filter(pk=self.member_membership.pk).exists())

    def test_admin_can_remove_another_admin(self) -> None:
        other_admin_membership = create_membership(
            self.organization, "admin2@example.com", OrganizationMembership.Role.ADMIN
        )
        self.client.force_login(self.admin)

        response = self.client.post(reverse("organizations:settings-member-remove", args=[other_admin_membership.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertFalse(OrganizationMembership.objects.filter(pk=other_admin_membership.pk).exists())

    def test_owner_cannot_remove_themselves(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(reverse("organizations:settings-member-remove", args=[self.owner_membership.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertTrue(OrganizationMembership.objects.filter(pk=self.owner_membership.pk).exists())

    def test_member_cannot_remove_anyone(self) -> None:
        self.client.force_login(self.member)

        response = self.client.post(reverse("organizations:settings-member-remove", args=[self.admin_membership.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertTrue(OrganizationMembership.objects.filter(pk=self.admin_membership.pk).exists())


class MemberTransferOwnershipViewTests(OrganizationViewTestCase):
    """Tests for MemberTransferOwnershipView."""

    def test_owner_can_transfer_ownership(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("organizations:settings-member-transfer-ownership", args=[self.member_membership.pk])
        )

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:settings-organization"))

        self.member_membership.refresh_from_db()
        self.owner_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, OrganizationMembership.Role.OWNER)
        self.assertEqual(self.owner_membership.role, OrganizationMembership.Role.ADMIN)

    def test_owner_cannot_transfer_to_themselves(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("organizations:settings-member-transfer-ownership", args=[self.owner_membership.pk])
        )

        self.assertEqual(response.status_code, HTTPStatus.FOUND)

        self.owner_membership.refresh_from_db()
        self.assertEqual(self.owner_membership.role, OrganizationMembership.Role.OWNER)

    def test_admin_cannot_transfer_ownership(self) -> None:
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("organizations:settings-member-transfer-ownership", args=[self.member_membership.pk])
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, OrganizationMembership.Role.MEMBER)
