from allauth.account.views import EmailView
from allauth.account.views import PasswordChangeView
from allauth.account.views import PasswordSetView
from allauth.socialaccount.views import ConnectionsView
from django.contrib import messages
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic.base import TemplateView
from django.views.generic.edit import UpdateView

from apps.accounts.forms import ProfileForm
from apps.accounts.models import User
from apps.organizations.mixins import OrganizationAccessMixin


class SettingsAccountView(OrganizationAccessMixin, TemplateView):
    """Account settings page: profile, email addresses, and social connections."""

    template_name = "accounts/settings_account.html"
    requires_subscription = False

    def get_context_data(self, **kwargs) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["profile_form"] = ProfileForm(instance=self.request.user)

        email_view = EmailView()
        email_view.setup(self.request)
        context.update(email_view.get_context_data())

        connections_view = ConnectionsView()
        connections_view.setup(self.request)
        context.update(connections_view.get_context_data())

        return context


class ProfileUpdateView(OrganizationAccessMixin, UpdateView):
    """Update the user's profile details."""

    template_name = "accounts/partials/settings_profile_details.html"
    http_method_names = ["post"]
    form_class = ProfileForm
    success_url = reverse_lazy("accounts:settings-account")
    requires_subscription = False

    def get_object(self) -> User:
        return self.request.user

    def form_valid(self, form: ProfileForm) -> HttpResponse:
        response = super().form_valid(form)
        messages.success(self.request, _("Profile updated successfully."))

        if self.request.htmx:
            return self.render_to_response(self.get_context_data())

        return response

    def get_context_data(self, **kwargs) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["profile_form"] = context["form"]
        return context


class SettingsSecurityView(OrganizationAccessMixin, TemplateView):
    """Security settings page with password change or set."""

    template_name = "accounts/settings_security.html"
    requires_subscription = False

    def get_context_data(self, **kwargs) -> dict[str, object]:
        context = super().get_context_data(**kwargs)

        password_view = PasswordChangeView() if self.request.user.has_usable_password() else PasswordSetView()
        password_view.setup(self.request)

        context["password_template"] = password_view.template_name
        context.update(password_view.get_context_data())

        return context
