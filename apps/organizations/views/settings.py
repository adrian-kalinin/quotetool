from typing import TYPE_CHECKING

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.urls import reverse_lazy
from django.views.generic import FormView
from django.views.generic import TemplateView
from django.views.generic import UpdateView

from apps.core.http import AuthenticatedHttpRequest
from apps.organizations.forms import InviteMemberForm
from apps.organizations.forms import OrganizationForm
from apps.organizations.mixins import OrganizationAccessMixin
from apps.organizations.models import Organization
from apps.organizations.models import OrganizationInvitation
from apps.organizations.models import OrganizationMembership
from apps.organizations.services import change_member_role
from apps.organizations.services import remove_member
from apps.organizations.services import resend_organization_invitation
from apps.organizations.services import revoke_organization_invitation
from apps.organizations.services import send_organization_invitation
from apps.organizations.services import transfer_organization_ownership


class OrganizationSettingsContextMixin:
    """Provide the viewer's membership plus members/invitations context for settings views."""

    if TYPE_CHECKING:
        request: AuthenticatedHttpRequest

    _user_membership: OrganizationMembership | None = None

    def get_user_membership(self) -> OrganizationMembership:
        if self._user_membership is None:
            self._user_membership = OrganizationMembership.objects.get(
                user=self.request.user, organization=self.request.user.active_organization
            )
        return self._user_membership

    def get_invitation_context(self) -> dict[str, object]:
        membership = self.get_user_membership()
        context = {"is_manager": membership.is_manager, "pending_invitations": []}

        if membership.is_manager:
            context["pending_invitations"] = OrganizationInvitation.objects.filter(
                organization=self.request.user.active_organization, status=OrganizationInvitation.Status.PENDING
            )

        return context

    def _member_actions(self, viewer: OrganizationMembership, membership: OrganizationMembership) -> set[str]:
        """Return the member-management actions `viewer` may take on `membership`."""
        actions: set[str] = set()

        if (
            viewer.is_manager
            and membership.user_id != viewer.user_id
            and membership.role != OrganizationMembership.Role.OWNER
        ):
            if viewer.role == OrganizationMembership.Role.OWNER:
                actions.add("transfer_ownership")

            actions.add("make_admin" if membership.role == OrganizationMembership.Role.MEMBER else "make_member")
            actions.add("remove")

        return actions

    def get_members_context(self) -> dict[str, object]:
        viewer = self.get_user_membership()
        memberships = (
            OrganizationMembership.objects.select_related("user")
            .filter(organization=self.request.user.active_organization)
            .order_by("user__email")
        )

        return {
            "memberships": [(membership, self._member_actions(viewer, membership)) for membership in memberships],
            "user_membership": viewer,
        }


class SettingsOrganizationView(OrganizationAccessMixin, OrganizationSettingsContextMixin, TemplateView):
    """Organization settings page with members and pending invitations."""

    template_name = "organizations/settings_organization.html"
    requires_subscription = False

    def get_context_data(self, **kwargs) -> dict[str, object]:
        context = super().get_context_data(**kwargs)

        context.update(self.get_members_context())
        context.update(self.get_invitation_context())

        if context["is_manager"]:
            context["invite_form"] = InviteMemberForm()
            context["organization_form"] = OrganizationForm(instance=self.request.user.active_organization)
        else:
            context["invite_form"] = None
            context["organization_form"] = None

        return context


class OrganizationUpdateView(OrganizationAccessMixin, UpdateView):
    """Update the active organization's details (owner/admin only)."""

    template_name = "organizations/partials/settings_organization_details.html"
    http_method_names = ["post"]
    form_class = OrganizationForm
    success_url = reverse_lazy("organizations:settings-organization")
    allowed_roles = (OrganizationMembership.Role.OWNER, OrganizationMembership.Role.ADMIN)
    requires_subscription = False

    def get_object(self) -> Organization:
        return self.request.user.active_organization

    def form_valid(self, form: OrganizationForm) -> HttpResponse:
        response = super().form_valid(form)
        messages.success(self.request, "Organization updated successfully.")

        if self.request.htmx:
            return self.render_to_response(self.get_context_data())

        return response

    def get_context_data(self, **kwargs) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["organization_form"] = context["form"]
        context["is_manager"] = True
        return context


class MemberInviteView(OrganizationAccessMixin, OrganizationSettingsContextMixin, FormView):
    """Invite a new member to the active organization (owner/admin only)."""

    template_name = "organizations/partials/settings_invitations.html"
    http_method_names = ["post"]
    form_class = InviteMemberForm
    success_url = reverse_lazy("organizations:settings-organization")
    allowed_roles = (OrganizationMembership.Role.OWNER, OrganizationMembership.Role.ADMIN)
    requires_subscription = False

    def form_valid(self, form: InviteMemberForm) -> HttpResponse:
        already_member = OrganizationMembership.objects.filter(
            organization=self.request.user.active_organization,
            user__email__iexact=form.cleaned_data["email"],
        ).exists()

        if already_member:
            messages.info(self.request, "That user is already a member of this organization.")
        else:
            invitations_url = self.request.build_absolute_uri(reverse("organizations:invitations"))
            send_organization_invitation(form.cleaned_data["email"], self.request.user, invitations_url)
            messages.success(self.request, f"Invitation sent to {form.cleaned_data['email']}.")

        if self.request.htmx:
            return self.render_to_response(self.get_context_data(form=InviteMemberForm()))

        return super().form_valid(form)

    def get_context_data(self, **kwargs) -> dict[str, object]:
        context = super().get_context_data(**kwargs)

        context["invite_form"] = kwargs.get("form", context["form"])
        context.update(self.get_invitation_context())

        return context


class BaseOrganizationInvitationActionView(OrganizationAccessMixin, OrganizationSettingsContextMixin, TemplateView):
    template_name = "organizations/partials/settings_invitations.html"
    http_method_names = ["post"]
    allowed_roles = (OrganizationMembership.Role.OWNER, OrganizationMembership.Role.ADMIN)
    requires_subscription = False

    def get_target_invitation(self, invitation_id: int) -> OrganizationInvitation | None:
        return OrganizationInvitation.objects.filter(
            id=invitation_id,
            organization=self.request.user.active_organization,
            status=OrganizationInvitation.Status.PENDING,
        ).first()

    def get_context_data(self, **kwargs) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["invite_form"] = InviteMemberForm()
        context.update(self.get_invitation_context())
        return context

    def render_invitations(self) -> HttpResponse:
        if self.request.htmx:
            return self.render_to_response(self.get_context_data())
        return redirect("organizations:settings-organization")


class InvitationRevokeView(BaseOrganizationInvitationActionView):
    """Revoke a pending invitation so it can no longer be accepted."""

    def post(self, request: AuthenticatedHttpRequest, invitation_id: int, *_, **__) -> HttpResponse:
        invitation = self.get_target_invitation(invitation_id)

        if invitation is None:
            messages.error(request, "That invitation is no longer pending.")
            return self.render_invitations()

        try:
            revoke_organization_invitation(invitation)
        except ValueError as exc:
            messages.error(request, str(exc))
            return self.render_invitations()

        messages.success(request, f"Revoked the invitation for {invitation.email}.")

        return self.render_invitations()


class InvitationResendView(BaseOrganizationInvitationActionView):
    """Re-send a pending invitation, extending its expiry."""

    def post(self, request: AuthenticatedHttpRequest, invitation_id: int, *_, **__) -> HttpResponse:
        invitation = self.get_target_invitation(invitation_id)

        if invitation is None:
            messages.error(request, "That invitation is no longer pending.")
            return self.render_invitations()

        invitations_url = request.build_absolute_uri(reverse("organizations:invitations"))

        try:
            resend_organization_invitation(invitation, invitations_url)
        except ValueError as exc:
            messages.error(request, str(exc))
            return self.render_invitations()

        messages.success(request, f"Resent the invitation to {invitation.email}.")

        return self.render_invitations()


class BaseMembershipActionView(OrganizationAccessMixin, OrganizationSettingsContextMixin, TemplateView):
    template_name = "organizations/partials/settings_members.html"
    http_method_names = ["post"]
    allowed_roles = (OrganizationMembership.Role.OWNER, OrganizationMembership.Role.ADMIN)
    requires_subscription = False

    def get_target_membership(self, membership_id: int) -> OrganizationMembership | None:
        return (
            OrganizationMembership.objects.select_related("user")
            .filter(id=membership_id, organization=self.request.user.active_organization)
            .first()
        )

    def get_context_data(self, **kwargs) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context.update(self.get_members_context())
        return context

    def render_members(self) -> HttpResponse:
        if self.request.htmx:
            return self.render_to_response(self.get_context_data())
        return redirect("organizations:settings-organization")


class MemberRoleUpdateView(BaseMembershipActionView):
    """Change a member's role between admin and member (managers only)."""

    allowed_roles = (OrganizationMembership.Role.OWNER, OrganizationMembership.Role.ADMIN)

    def post(self, request: AuthenticatedHttpRequest, membership_id: int, *_, **__) -> HttpResponse:
        membership = self.get_target_membership(membership_id)

        if membership is None:
            messages.error(request, "That member is no longer part of this organization.")
            return self.render_members()

        try:
            change_member_role(membership, request.POST.get("role", ""))
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Updated role for {membership.user.email}.")

        return self.render_members()


class MemberRemoveView(BaseMembershipActionView):
    """Remove a member from the organization (owner/admin, hierarchy-aware)."""

    def post(self, request: AuthenticatedHttpRequest, membership_id: int, *_, **__) -> HttpResponse:
        membership = self.get_target_membership(membership_id)

        if membership is None:
            messages.error(request, "That member is no longer part of this organization.")
            return self.render_members()

        email = membership.user.email

        try:
            remove_member(self.get_user_membership(), membership)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Removed {email} from the organization.")

        return self.render_members()


class MemberTransferOwnershipView(BaseMembershipActionView):
    """Hand ownership to another member; the current owner becomes an admin (owner only)."""

    allowed_roles = (OrganizationMembership.Role.OWNER,)

    def post(self, request: AuthenticatedHttpRequest, membership_id: int, *_, **__) -> HttpResponse:
        membership = self.get_target_membership(membership_id)

        if membership is None:
            messages.error(request, "That member is no longer part of this organization.")
            return self.render_members()

        try:
            transfer_organization_ownership(self.get_user_membership(), membership)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Ownership transferred to {membership.user.email}. You are now an admin.")

        return self.render_members()
