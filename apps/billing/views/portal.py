import logging

from django.contrib import messages
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View

from apps.billing.client import get_polar_client
from apps.core.http import AuthenticatedHttpRequest
from apps.organizations.mixins import OrganizationAccessMixin
from apps.organizations.models import OrganizationMembership

logger = logging.getLogger(__name__)


class PortalRedirectView(OrganizationAccessMixin, View):
    """Create a customer session and redirect to the hosted Polar customer portal."""

    http_method_names = ["post"]
    allowed_roles = (OrganizationMembership.Role.OWNER, OrganizationMembership.Role.ADMIN)
    requires_subscription = False

    def post(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        organization = request.user.active_organization

        try:
            session = get_polar_client().customer_sessions.create(  # type: ignore[reportCallIssue]
                customer_external_id=str(organization.uuid),
                return_url=request.build_absolute_uri(reverse("billing:settings-billing")),
            )
        except Exception:
            logger.exception("Failed to create Polar customer session for organization %s", organization.uuid)
            messages.error(request, _("Could not open the customer portal. Please try again later."))
            return redirect("billing:settings-billing")

        response = HttpResponseRedirect(session.customer_portal_url)
        response.status_code = 303
        return response
