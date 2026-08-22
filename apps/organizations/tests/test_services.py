from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.organizations.models import OrganizationInvitation
from apps.organizations.models import OrganizationMembership
from apps.organizations.services import accept_organization_invitation
from apps.organizations.services import change_member_role
from apps.organizations.services import decline_organization_invitation
from apps.organizations.services import leave_organization
from apps.organizations.services import remove_member
from apps.organizations.services import resend_organization_invitation
from apps.organizations.services import revoke_organization_invitation
from apps.organizations.services import send_organization_invitation
from apps.organizations.services import transfer_organization_ownership

INVITATIONS_URL = "https://example.com/app/invitations/"


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


class MembershipTestCase(TestCase):
    """Base setup: one organization with an owner, an admin, and a member."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        cls.owner = User.objects.create_user("owner@example.com", "test-password")
        cls.owner.active_organization = cls.organization
        cls.owner.save(update_fields=["active_organization"])
        cls.owner_membership = OrganizationMembership.objects.create(
            user=cls.owner, organization=cls.organization, role=OrganizationMembership.Role.OWNER
        )
        cls.admin_membership = OrganizationMembership.objects.create(
            user=User.objects.create_user("admin@example.com", "test-password"),
            organization=cls.organization,
            role=OrganizationMembership.Role.ADMIN,
        )
        cls.member_membership = OrganizationMembership.objects.create(
            user=User.objects.create_user("member@example.com", "test-password"),
            organization=cls.organization,
            role=OrganizationMembership.Role.MEMBER,
        )


class SendOrganizationInvitationTests(MembershipTestCase):
    """Tests for send_organization_invitation."""

    def test_creates_pending_invitation_expiring_in_seven_days(self) -> None:
        send_organization_invitation("new@example.com", self.owner, INVITATIONS_URL)

        invitation = OrganizationInvitation.objects.get(organization=self.organization, email="new@example.com")
        self.assertEqual(invitation.invited_by, self.owner)
        self.assertEqual(invitation.status, OrganizationInvitation.Status.PENDING)
        self.assertGreaterEqual(invitation.expires_at, timezone.now() + timedelta(days=7, minutes=-1))
        self.assertLessEqual(invitation.expires_at, timezone.now() + timedelta(days=7))

    def test_sends_invitation_email_on_commit(self) -> None:
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            send_organization_invitation("new@example.com", self.owner, INVITATIONS_URL)

        self.assertEqual(len(callbacks), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new@example.com"])
        self.assertEqual(mail.outbox[0].subject, "You've been invited to join Acme Inc.")
        self.assertIn(INVITATIONS_URL, mail.outbox[0].body)

    def test_email_is_not_sent_before_commit(self) -> None:
        with self.captureOnCommitCallbacks():
            send_organization_invitation("new@example.com", self.owner, INVITATIONS_URL)

        self.assertEqual(len(mail.outbox), 0)

    def test_revokes_prior_pending_invitation_for_same_email(self) -> None:
        old_invitation = create_invitation(self.organization, "new@example.com", self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            send_organization_invitation("new@example.com", self.owner, INVITATIONS_URL)

        old_invitation.refresh_from_db()
        self.assertEqual(old_invitation.status, OrganizationInvitation.Status.REVOKED)
        pending = OrganizationInvitation.objects.filter(
            organization=self.organization, email="new@example.com", status=OrganizationInvitation.Status.PENDING
        )
        self.assertEqual(pending.count(), 1)

    def test_revokes_prior_pending_invitation_case_insensitively(self) -> None:
        old_invitation = create_invitation(self.organization, "New@Example.com", self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            send_organization_invitation("new@example.com", self.owner, INVITATIONS_URL)

        old_invitation.refresh_from_db()
        self.assertEqual(old_invitation.status, OrganizationInvitation.Status.REVOKED)


class ResendOrganizationInvitationTests(MembershipTestCase):
    """Tests for resend_organization_invitation."""

    def test_extends_expiry_and_resends_email(self) -> None:
        invitation = create_invitation(self.organization, "new@example.com", self.owner, expires_in_days=2)

        with self.captureOnCommitCallbacks(execute=True):
            resend_organization_invitation(invitation, INVITATIONS_URL)

        invitation.refresh_from_db()
        self.assertGreaterEqual(invitation.expires_at, timezone.now() + timedelta(days=7, minutes=-1))
        self.assertLessEqual(invitation.expires_at, timezone.now() + timedelta(days=7))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new@example.com"])


class RevokeOrganizationInvitationTests(MembershipTestCase):
    """Tests for revoke_organization_invitation."""

    def test_marks_invitation_revoked(self) -> None:
        invitation = create_invitation(self.organization, "new@example.com", self.owner)

        revoke_organization_invitation(invitation)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.REVOKED)


class AcceptOrganizationInvitationTests(TestCase):
    """Tests for accept_organization_invitation."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        cls.inviter = User.objects.create_user("owner@example.com", "test-password")
        cls.invitee = User.objects.create_user("invitee@example.com", "test-password")

    def test_creates_membership_and_switches_active_organization(self) -> None:
        invitation = create_invitation(self.organization, self.invitee.email, self.inviter)

        accept_organization_invitation(invitation, self.invitee)

        membership = OrganizationMembership.objects.get(user=self.invitee, organization=self.organization)
        self.assertEqual(membership.role, OrganizationMembership.Role.MEMBER)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.ACCEPTED)
        self.assertIsNotNone(invitation.accepted_at)

        self.invitee.refresh_from_db()
        self.assertEqual(self.invitee.active_organization, self.organization)

    def test_matches_email_case_insensitively(self) -> None:
        invitation = create_invitation(self.organization, "Invitee@Example.com", self.inviter)

        accept_organization_invitation(invitation, self.invitee)

        self.assertTrue(
            OrganizationMembership.objects.filter(user=self.invitee, organization=self.organization).exists()
        )

    def test_keeps_existing_membership_role(self) -> None:
        invitation = create_invitation(self.organization, self.invitee.email, self.inviter)
        existing = OrganizationMembership.objects.create(
            user=self.invitee, organization=self.organization, role=OrganizationMembership.Role.ADMIN
        )

        accept_organization_invitation(invitation, self.invitee)

        existing.refresh_from_db()
        self.assertEqual(existing.role, OrganizationMembership.Role.ADMIN)
        memberships = OrganizationMembership.objects.filter(user=self.invitee, organization=self.organization)
        self.assertEqual(memberships.count(), 1)

    def test_rejects_mismatched_email(self) -> None:
        invitation = create_invitation(self.organization, "someone-else@example.com", self.inviter)

        with self.assertRaisesMessage(ValueError, "User email does not match invitation email."):
            accept_organization_invitation(invitation, self.invitee)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.PENDING)
        self.assertFalse(
            OrganizationMembership.objects.filter(user=self.invitee, organization=self.organization).exists()
        )


class DeclineOrganizationInvitationTests(TestCase):
    """Tests for decline_organization_invitation."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(name="Acme Inc.")
        cls.inviter = User.objects.create_user("owner@example.com", "test-password")
        cls.invitee = User.objects.create_user("invitee@example.com", "test-password")

    def test_marks_invitation_declined(self) -> None:
        invitation = create_invitation(self.organization, self.invitee.email, self.inviter)

        decline_organization_invitation(invitation, self.invitee)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.DECLINED)

    def test_rejects_mismatched_email(self) -> None:
        invitation = create_invitation(self.organization, "someone-else@example.com", self.inviter)

        with self.assertRaisesMessage(ValueError, "User email does not match invitation email."):
            decline_organization_invitation(invitation, self.invitee)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.PENDING)


class ChangeMemberRoleTests(MembershipTestCase):
    """Tests for change_member_role."""

    def test_promotes_member_to_admin(self) -> None:
        change_member_role(self.member_membership, OrganizationMembership.Role.ADMIN)

        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, OrganizationMembership.Role.ADMIN)

    def test_demotes_admin_to_member(self) -> None:
        change_member_role(self.admin_membership, OrganizationMembership.Role.MEMBER)

        self.admin_membership.refresh_from_db()
        self.assertEqual(self.admin_membership.role, OrganizationMembership.Role.MEMBER)

    def test_rejects_changing_the_owners_role(self) -> None:
        with self.assertRaisesMessage(ValueError, "The owner's role cannot be changed."):
            change_member_role(self.owner_membership, OrganizationMembership.Role.MEMBER)

        self.owner_membership.refresh_from_db()
        self.assertEqual(self.owner_membership.role, OrganizationMembership.Role.OWNER)

    def test_rejects_invalid_role(self) -> None:
        with self.assertRaisesMessage(ValueError, "Invalid role."):
            change_member_role(self.member_membership, OrganizationMembership.Role.OWNER)

        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, OrganizationMembership.Role.MEMBER)


class LeaveOrganizationTests(MembershipTestCase):
    """Tests for leave_organization."""

    def test_member_can_leave(self) -> None:
        leave_organization(self.member_membership)

        self.assertFalse(OrganizationMembership.objects.filter(pk=self.member_membership.pk).exists())

    def test_admin_can_leave(self) -> None:
        leave_organization(self.admin_membership)

        self.assertFalse(OrganizationMembership.objects.filter(pk=self.admin_membership.pk).exists())

    def test_owner_cannot_leave(self) -> None:
        with self.assertRaisesMessage(ValueError, "The owner cannot leave the organization. Transfer ownership first."):
            leave_organization(self.owner_membership)

        self.assertTrue(OrganizationMembership.objects.filter(pk=self.owner_membership.pk).exists())


class RemoveMemberTests(MembershipTestCase):
    """Tests for remove_member."""

    def test_owner_removes_member(self) -> None:
        remove_member(self.owner_membership, self.member_membership)

        self.assertFalse(OrganizationMembership.objects.filter(pk=self.member_membership.pk).exists())

    def test_owner_removes_admin(self) -> None:
        remove_member(self.owner_membership, self.admin_membership)

        self.assertFalse(OrganizationMembership.objects.filter(pk=self.admin_membership.pk).exists())

    def test_admin_removes_member(self) -> None:
        remove_member(self.admin_membership, self.member_membership)

        self.assertFalse(OrganizationMembership.objects.filter(pk=self.member_membership.pk).exists())

    def test_admin_can_remove_another_admin(self) -> None:
        other_admin_membership = OrganizationMembership.objects.create(
            user=User.objects.create_user("admin2@example.com", "test-password"),
            organization=self.organization,
            role=OrganizationMembership.Role.ADMIN,
        )
        remove_member(self.admin_membership, other_admin_membership)

        self.assertFalse(OrganizationMembership.objects.filter(pk=other_admin_membership.pk).exists())

    def test_owner_cannot_be_removed(self) -> None:
        with self.assertRaisesMessage(ValueError, "The owner cannot be removed from the organization."):
            remove_member(self.admin_membership, self.owner_membership)

        self.assertTrue(OrganizationMembership.objects.filter(pk=self.owner_membership.pk).exists())

    def test_cannot_remove_yourself(self) -> None:
        with self.assertRaisesMessage(ValueError, "You cannot remove yourself from the organization."):
            remove_member(self.owner_membership, self.owner_membership)

        self.assertTrue(OrganizationMembership.objects.filter(pk=self.owner_membership.pk).exists())


class TransferOrganizationOwnershipTests(MembershipTestCase):
    """Tests for transfer_organization_ownership."""

    def test_transfers_ownership_and_demotes_previous_owner(self) -> None:
        transfer_organization_ownership(self.owner_membership, self.member_membership)

        self.owner_membership.refresh_from_db()
        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, OrganizationMembership.Role.OWNER)
        self.assertEqual(self.owner_membership.role, OrganizationMembership.Role.ADMIN)

    def test_rejects_transfer_to_self(self) -> None:
        with self.assertRaisesMessage(ValueError, "You already own this organization."):
            transfer_organization_ownership(self.owner_membership, self.owner_membership)

        self.owner_membership.refresh_from_db()
        self.assertEqual(self.owner_membership.role, OrganizationMembership.Role.OWNER)
