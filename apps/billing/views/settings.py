from django.views.generic.base import TemplateView

from apps.billing.prices import sellable_plans
from apps.organizations.mixins import OrganizationAccessMixin
from apps.organizations.models import OrganizationMembership


class BillingSettingsView(OrganizationAccessMixin, TemplateView):
    """Billing page: current subscription and sellable plan cards."""

    template_name = "billing/settings.html"
    requires_subscription = False

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)

        context["subscription"] = getattr(self.request.user.active_organization, "subscription", None)
        context["is_manager"] = self._is_manager()
        context["plans"] = sellable_plans()

        return context

    def _is_manager(self) -> bool:
        return OrganizationMembership.objects.get(
            user=self.request.user, organization=self.request.user.active_organization
        ).is_manager
