from django.views.generic import RedirectView
from django.views.generic.base import TemplateView

from apps.organizations.mixins import OrganizationAccessMixin


class IndexView(RedirectView):
    """Redirects to the dashboard after login."""

    pattern_name = "dashboard:dashboard"


class DashboardView(OrganizationAccessMixin, TemplateView):
    """Main in-app landing page after login."""

    template_name = "dashboard/dashboard.html"
