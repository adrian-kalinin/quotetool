from django.views.generic.base import TemplateView

from apps.billing.prices import sellable_plans


class LandingPageView(TemplateView):
    """Public marketing landing page."""

    template_name = "pages/landing.html"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["plans"] = sellable_plans(public_only=True)
        return context
