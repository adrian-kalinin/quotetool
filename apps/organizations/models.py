import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Organization(models.Model):
    name = models.CharField(max_length=100)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    memberships: models.QuerySet["OrganizationMembership"]

    def __str__(self) -> str:
        return self.name

    @property
    def has_active_subscription(self) -> bool:
        subscription = getattr(self, "subscription", None)
        return subscription is not None and subscription.is_active


class OrganizationMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", _("Owner")
        ADMIN = "admin", _("Admin")
        MEMBER = "member", _("Member")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    user_id: int
    organization_id: int

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization"],
                name="unique_user_organization_membership",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.organization} · {self.role}"

    @property
    def is_manager(self) -> bool:
        return self.role in (OrganizationMembership.Role.OWNER, OrganizationMembership.Role.ADMIN)


class OrganizationInvitationQuerySet(models.QuerySet["OrganizationInvitation"]):
    """QuerySet for OrganizationInvitation."""

    def pending(self) -> "OrganizationInvitationQuerySet":
        """Return invitations still open to be accepted (pending and not expired)."""
        return self.filter(status=OrganizationInvitation.Status.PENDING, expires_at__gt=timezone.now())


class OrganizationInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        ACCEPTED = "accepted", _("Accepted")
        REVOKED = "revoked", _("Revoked")
        DECLINED = "declined", _("Declined")

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField()
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_invitations",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    organization_id: int
    invited_by_id: int

    objects = OrganizationInvitationQuerySet.as_manager()

    class Meta:
        verbose_name = _("Invitation")
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"],
                condition=models.Q(status="pending"),
                name="unique_pending_invitation_per_org_email",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.email} → {self.organization} ({self.status})"
