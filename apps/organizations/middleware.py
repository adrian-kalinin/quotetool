from collections.abc import Callable
from typing import TYPE_CHECKING
from typing import cast

from django.http import HttpResponse

from apps.core.http import HttpRequest
from apps.organizations.models import OrganizationMembership

if TYPE_CHECKING:
    from apps.accounts.models import User


class ActiveOrganizationIntegrityMiddleware:
    """If the user's `active_organization` no longer matches a membership, null it out."""

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            user = cast("User", request.user)
            original_organization_id = user.active_organization_id

            if original_organization_id is not None:
                is_member = OrganizationMembership.objects.filter(
                    user=user, organization_id=original_organization_id
                ).exists()

                if not is_member:
                    user.active_organization_id = None

            if user.active_organization_id is None:
                membership = OrganizationMembership.objects.filter(user=user).first()

                if membership is not None:
                    user.active_organization_id = membership.organization_id

            if user.active_organization_id != original_organization_id:
                user.save(update_fields=["active_organization", "updated_at"])

        return self.get_response(request)
