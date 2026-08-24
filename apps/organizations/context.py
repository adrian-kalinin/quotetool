from typing import TYPE_CHECKING
from typing import cast

from django.http import HttpRequest

from apps.organizations.models import OrganizationInvitation
from apps.organizations.models import OrganizationMembership

if TYPE_CHECKING:
    from apps.accounts.models import User


def organizations(request: HttpRequest) -> dict[str, object]:
    """Add the active organization, available organizations, and pending invitation count."""
    if not request.user.is_authenticated:
        return {}

    user = cast("User", request.user)

    memberships = list(
        OrganizationMembership.objects.select_related("organization")
        .filter(user=user)
        .order_by("organization__name")
        .prefetch_related("organization__subscription")
    )
    organizations_list = [membership.organization for membership in memberships]
    organizations_by_id = {organization.pk: organization for organization in organizations_list}

    # Pick the active org from the prefetched list so its subscription is cached;
    # fall back to the FK for the (middleware-prevented) inconsistent state.
    active_organization = organizations_by_id.get(user.active_organization_id, user.active_organization)

    pending_invitations_count = OrganizationInvitation.objects.pending().filter(email__iexact=user.email).count()  # type: ignore[ reportAttributeAccessIssue]

    return {
        "active_organization": active_organization,
        "available_organizations": organizations_list,
        "pending_invitations_count": pending_invitations_count,
    }
