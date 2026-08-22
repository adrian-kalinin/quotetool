from datetime import timedelta

from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.organizations.models import OrganizationInvitation
from apps.organizations.models import OrganizationMembership


def _send_invitation_email(invitation: OrganizationInvitation, invitations_url: str) -> None:
    """Render and queue the invitation email once the surrounding transaction commits."""
    context = {
        "organization": invitation.organization,
        "invited_by": invitation.invited_by,
        "invitations_url": invitations_url,
    }
    subject = render_to_string("organizations/emails/invitation_subject.txt", context).strip()
    message = render_to_string("organizations/emails/invitation_message.txt", context)

    # Send only after the transaction commits, so no email goes out for a rolled-back invitation.
    transaction.on_commit(
        lambda: send_mail(subject=subject, message=message, from_email=None, recipient_list=[invitation.email])
    )


@transaction.atomic
def send_organization_invitation(email: str, invited_by: User, invitations_url: str) -> None:
    """Invite an email to the inviter's active organization, revoking prior pending invites."""
    # Lock the organization so concurrent invites for the same org cannot race the
    # partial unique constraint on (organization, email) where status='pending'.
    organization = Organization.objects.select_for_update().get(pk=invited_by.active_organization_id)
    email = email.lower()

    # Revoke any prior invitations for this email/organization pair
    OrganizationInvitation.objects.filter(
        organization=organization, email__iexact=email, status=OrganizationInvitation.Status.PENDING
    ).update(status=OrganizationInvitation.Status.REVOKED)

    expires_at = timezone.now() + timedelta(days=7)
    invitation = OrganizationInvitation.objects.create(
        organization=organization, email=email, invited_by=invited_by, expires_at=expires_at
    )

    _send_invitation_email(invitation, invitations_url)


@transaction.atomic
def resend_organization_invitation(invitation: OrganizationInvitation, invitations_url: str) -> None:
    """Re-send a pending invitation, extending its expiry."""
    _ensure_pending(invitation)

    invitation.expires_at = timezone.now() + timedelta(days=7)
    invitation.save(update_fields=["expires_at"])

    _send_invitation_email(invitation, invitations_url)


def revoke_organization_invitation(invitation: OrganizationInvitation) -> None:
    """Mark the invitation as revoked so it can no longer be accepted."""
    _ensure_pending(invitation)

    invitation.status = OrganizationInvitation.Status.REVOKED
    invitation.save(update_fields=["status"])


@transaction.atomic
def accept_organization_invitation(invitation: OrganizationInvitation, user: User) -> None:
    """Accept the invitation: create the membership and switch the user to the organization."""
    if user.email.lower() != invitation.email.lower():
        raise ValueError("User email does not match invitation email.")

    _ensure_pending(invitation)

    OrganizationMembership.objects.get_or_create(
        user=user,
        organization=invitation.organization,
        defaults={"role": OrganizationMembership.Role.MEMBER},
    )
    invitation.status = OrganizationInvitation.Status.ACCEPTED
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at", "status"])

    user.active_organization = invitation.organization
    user.save(update_fields=["active_organization", "updated_at"])


def decline_organization_invitation(invitation: OrganizationInvitation, user: User) -> None:
    """Mark the invitation as declined."""
    if user.email.lower() != invitation.email.lower():
        raise ValueError("User email does not match invitation email.")

    _ensure_pending(invitation)

    invitation.status = OrganizationInvitation.Status.DECLINED
    invitation.save(update_fields=["status"])


def _ensure_pending(invitation: OrganizationInvitation) -> None:
    """Raise ValueError unless the invitation is still open to be acted on."""
    if invitation.status != OrganizationInvitation.Status.PENDING:
        raise ValueError("This invitation is no longer pending.")
    if invitation.expires_at <= timezone.now():
        raise ValueError("This invitation has expired.")


def change_member_role(membership: OrganizationMembership, new_role: str) -> None:
    """Change a non-owner membership to admin or member."""
    if membership.role == OrganizationMembership.Role.OWNER:
        raise ValueError("The owner's role cannot be changed.")

    if new_role not in (OrganizationMembership.Role.ADMIN, OrganizationMembership.Role.MEMBER):
        raise ValueError("Invalid role.")

    membership.role = new_role
    membership.save(update_fields=["role", "updated_at"])


def remove_member(actor: OrganizationMembership, membership: OrganizationMembership) -> None:
    """Remove a member from the organization, respecting the role hierarchy."""
    if actor.pk == membership.pk:
        raise ValueError("You cannot remove yourself from the organization.")

    if membership.role == OrganizationMembership.Role.OWNER:
        raise ValueError("The owner cannot be removed from the organization.")

    membership.delete()


@transaction.atomic
def transfer_organization_ownership(owner: OrganizationMembership, membership: OrganizationMembership) -> None:
    """Make another member the owner; the current owner becomes an admin."""
    if owner.pk == membership.pk:
        raise ValueError("You already own this organization.")

    owner.role = OrganizationMembership.Role.ADMIN
    owner.save(update_fields=["role", "updated_at"])

    membership.role = OrganizationMembership.Role.OWNER
    membership.save(update_fields=["role", "updated_at"])


def leave_organization(membership: OrganizationMembership) -> None:
    """Leave an organization voluntarily; the owner must transfer ownership first."""
    if membership.role == OrganizationMembership.Role.OWNER:
        raise ValueError("The owner cannot leave the organization. Transfer ownership first.")

    membership.delete()
