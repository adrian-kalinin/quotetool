import logging

from django.contrib import messages
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View

from apps.billing.client import get_polar_client
from apps.billing.plans import PlanKey
from apps.billing.plans import product_id_for
from apps.billing.services import sync_subscription_state
from apps.core.http import AuthenticatedHttpRequest
from apps.organizations.mixins import OrganizationAccessMixin
from apps.organizations.models import OrganizationMembership

logger = logging.getLogger(__name__)


class CheckoutView(OrganizationAccessMixin, View):
    """Start a hosted Polar checkout for the selected plan."""

    http_method_names = ["post"]
    allowed_roles = (OrganizationMembership.Role.OWNER, OrganizationMembership.Role.ADMIN)
    requires_subscription = False

    def post(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        organization = request.user.active_organization

        try:
            plan_key = PlanKey(request.POST.get("plan_key", ""))
        except ValueError:
            messages.error(request, _("Invalid plan."))
            return redirect("billing:settings-billing")

        subscription = getattr(organization, "subscription", None)
        if subscription is not None and subscription.is_active:
            messages.info(request, _("You already have an active subscription; manage it from the portal."))
            return redirect("billing:settings-billing")

        product_id = product_id_for(plan_key)
        if product_id is None:
            messages.error(request, _("This plan is not available for purchase."))
            return redirect("billing:settings-billing")

        try:
            checkout = get_polar_client().checkouts.create(
                products=[product_id],
                customer_email=request.user.email,
                external_customer_id=str(organization.uuid),
                success_url=request.build_absolute_uri(reverse("billing:checkout-success")),
            )
        except Exception:
            logger.exception("Failed to create Polar checkout for organization %s", organization.uuid)
            messages.error(request, _("Could not start checkout. Please try again later."))
            return redirect("billing:settings-billing")

        response = HttpResponseRedirect(checkout.url)
        response.status_code = 303
        return response


class CheckoutSuccessView(OrganizationAccessMixin, View):
    """Return from checkout: sync once in case the webhook has not arrived, then redirect."""

    http_method_names = ["get"]
    requires_subscription = False

    def get(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        sync_subscription_state(request.user.active_organization)
        messages.success(request, _("Subscription activated successfully."))
        return redirect("billing:settings-billing")
