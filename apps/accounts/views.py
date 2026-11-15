from allauth.account.views import EmailView
from allauth.account.views import PasswordChangeView
from allauth.account.views import PasswordSetView
from allauth.socialaccount.views import ConnectionsView
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic.base import TemplateView
from django.views.generic.edit import UpdateView
from django_htmx.http import HttpResponseClientRefresh

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
        language_changed = "language" in form.changed_data

        response = super().form_valid(form)

        messages.success(self.request, _("Profile updated successfully."))

        if self.request.htmx:
            if language_changed:
                response = HttpResponseClientRefresh()
            else:
                response = self.render_to_response(self.get_context_data())

        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, form.cleaned_data["language"])
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

        has_password = self.request.user.has_usable_password()
        password_view = PasswordChangeView() if has_password else PasswordSetView()
        password_view.setup(self.request)

        context["password_template"] = (
            "account/partials/password_change.html" if has_password else "account/partials/password_set.html"
        )
        context.update(password_view.get_context_data())

        return context
