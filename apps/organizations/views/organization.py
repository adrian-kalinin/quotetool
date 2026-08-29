import uuid

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic.edit import CreateView

from apps.core.http import AuthenticatedHttpRequest
from apps.core.mixins import LoginRequiredMixin
from apps.organizations.forms import OrganizationForm
from apps.organizations.mixins import OrganizationAccessMixin
from apps.organizations.models import OrganizationInvitation
from apps.organizations.models import OrganizationMembership
from apps.organizations.services import leave_organization


class OnboardingView(LoginRequiredMixin, View):
    """Route new users to the dashboard, pending invitations, or organization creation."""

    def get(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        if request.user.active_organization_id:
            return redirect("dashboard:dashboard")

        has_pending = OrganizationInvitation.objects.pending().filter(email__iexact=request.user.email).exists()  # type: ignore[reportAttributeAccessIssue]

        if has_pending:
            return redirect("organizations:invitations")

        return redirect("organizations:organization-create")


class OrganizationCreateView(LoginRequiredMixin, CreateView):
    """Create an organization; the creator becomes its owner."""

    template_name = "organizations/create_organization.html"
    form_class = OrganizationForm
    success_url = reverse_lazy("dashboard:dashboard")

    @transaction.atomic
    def form_valid(self, form: OrganizationForm) -> HttpResponse:
        response = super().form_valid(form)

        OrganizationMembership.objects.create(
            user=self.request.user, organization=self.object, role=OrganizationMembership.Role.OWNER
        )
        self.request.user.active_organization = self.object
        self.request.user.save(update_fields=["active_organization", "updated_at"])
        messages.success(self.request, _("Organization created."))

        return response


class OrganizationSwitchView(LoginRequiredMixin, View):
    """Switch the user's active organization."""

    http_method_names = ["post"]

    def post(self, request: AuthenticatedHttpRequest, org_uuid: uuid.UUID, *_args, **_kwargs) -> HttpResponse:
        membership = (
            OrganizationMembership.objects.select_related("organization")
            .filter(user=request.user, organization__uuid=org_uuid)
            .first()
        )

        if membership is None:
            messages.error(request, _("You are not a member of that organization."))
            return redirect("dashboard:dashboard")

        request.user.active_organization = membership.organization
        request.user.save(update_fields=["active_organization", "updated_at"])
        messages.success(request, _("Switched to %(organization)s.") % {"organization": membership.organization.name})

        return redirect("dashboard:dashboard")


class OrganizationLeaveView(OrganizationAccessMixin, View):
    """Leave the active organization; the owner must transfer ownership first."""

    http_method_names = ["post"]
    requires_subscription = False

    def post(self, request: AuthenticatedHttpRequest, *_args, **_kwargs) -> HttpResponse:
        membership = (
            OrganizationMembership.objects.select_related("organization")
            .filter(user=request.user, organization=request.user.active_organization_id)
            .first()
        )

        if membership is None:
            messages.error(request, _("You are not a member of that organization."))
            return redirect("dashboard:dashboard")

        try:
            leave_organization(membership)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            request.user.active_organization = None
            request.user.save(update_fields=["active_organization", "updated_at"])
            messages.success(request, _("You left %(organization)s.") % {"organization": membership.organization.name})

        return redirect("dashboard:dashboard")
