from typing import TYPE_CHECKING
from typing import cast

from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBase
from django.shortcuts import redirect

from apps.accounts.models import User
from apps.core.http import AuthenticatedHttpRequest
from apps.core.http import HttpRequest
from apps.organizations.models import OrganizationMembership


class OrganizationAccessMixin(AccessMixin):
    """Requires the user to be authenticated and have an active organization, optionally checks user's role.

    With requires_subscription (default), the active organization must have an active
    subscription; lapsed organizations are redirected to the billing page.
    """

    allowed_roles: tuple[str, ...] | None = None
    requires_subscription: bool = True

    if TYPE_CHECKING:
        request: AuthenticatedHttpRequest

    def check_organization_permissions(self, user: User) -> None:
        if self.allowed_roles is None:
            return

        membership = OrganizationMembership.objects.filter(user=user, organization=user.active_organization).first()

        if membership is None or membership.role not in self.allowed_roles:
            raise PermissionDenied

    def check_subscription(self, user: User) -> bool:
        subscription = getattr(user.active_organization, "subscription", None)
        return subscription is not None and subscription.is_active

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponseBase:
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        user = cast("User", request.user)

        if user.active_organization_id is None:
            return redirect("organizations:onboarding")

        self.check_organization_permissions(user)

        if self.requires_subscription and not self.check_subscription(user):
            return redirect("billing:settings-billing")

        return super().dispatch(request, *args, **kwargs)  # type: ignore[reportAttributeAccessIssue]
