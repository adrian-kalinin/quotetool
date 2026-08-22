from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.core.http import AuthenticatedHttpRequest
from apps.core.mixins import LoginRequiredMixin
from apps.organizations.models import OrganizationInvitation
from apps.organizations.services import accept_organization_invitation
from apps.organizations.services import decline_organization_invitation


class InvitationListView(LoginRequiredMixin, TemplateView):
    """Show the user's pending organization invitations."""

    template_name = "organizations/invitations.html"

    def get_pending_invitations(self) -> list[OrganizationInvitation]:
        return list(
            OrganizationInvitation.objects.select_related("organization", "invited_by").filter(
                email__iexact=self.request.user.email,
                status=OrganizationInvitation.Status.PENDING,
                expires_at__gt=timezone.now(),
            )
        )

    def get(self, request: AuthenticatedHttpRequest, *args, **kwargs) -> HttpResponse:
        pending_invitations = self.get_pending_invitations()

        if not pending_invitations:
            if request.user.active_organization_id:
                return redirect("dashboard:dashboard")
            return redirect("organizations:organization-create")

        return super().get(request, *args, pending_invitations=pending_invitations, **kwargs)

    def get_context_data(self, **kwargs) -> dict[str, object]:
        pending_invitations = kwargs.pop("pending_invitations", [])
        context = super().get_context_data(**kwargs)
        context["pending_invitations"] = pending_invitations
        return context


class BaseInvitationActionView(LoginRequiredMixin, View):
    """Base for POST actions on the user's own pending invitations."""

    http_method_names = ["post"]

    def get_target_invitation(self, invitation_id: int) -> OrganizationInvitation | None:
        return (
            OrganizationInvitation.objects.select_related("organization")
            .filter(
                id=invitation_id,
                email__iexact=self.request.user.email,
                status=OrganizationInvitation.Status.PENDING,
                expires_at__gt=timezone.now(),
            )
            .first()
        )


class InvitationAcceptView(BaseInvitationActionView):
    """Accept an invitation and join its organization."""

    def post(self, request: AuthenticatedHttpRequest, invitation_id: int, *_, **__) -> HttpResponse:
        invitation = self.get_target_invitation(invitation_id)

        if invitation is None:
            messages.error(request, "That invitation is no longer available.")
            return redirect("organizations:invitations")

        try:
            accept_organization_invitation(invitation, request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("organizations:invitations")

        messages.success(request, f"You joined {invitation.organization.name}.")

        return redirect("dashboard:dashboard")


class InvitationDeclineView(BaseInvitationActionView):
    """Decline an invitation."""

    def post(self, request: AuthenticatedHttpRequest, invitation_id: int, *_, **__) -> HttpResponse:
        invitation = self.get_target_invitation(invitation_id)

        if invitation is None:
            messages.error(request, "That invitation is no longer available.")
            return redirect("organizations:invitations")

        try:
            decline_organization_invitation(invitation, request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("organizations:invitations")

        messages.info(request, "Invitation declined.")

        return redirect("organizations:invitations")
