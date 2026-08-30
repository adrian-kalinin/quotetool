from typing import TYPE_CHECKING
from typing import cast

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic.base import TemplateView
from django.views.generic.base import View

from apps.core.http import HttpRequest

if TYPE_CHECKING:
    from apps.accounts.models import User


class MessagesView(TemplateView):
    """Render queued Django messages as toast markup (fetched by htmx)."""

    template_name = "snippets/messages.html"

    def get_context_data(self, **kwargs) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["messages"] = messages.get_messages(self.request)
        return context


class SetLanguageView(View):
    """Set the active language: persist on the user model when authenticated, else store in a cookie."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest) -> HttpResponse:
        code = request.POST.get("language", "")
        response = HttpResponseRedirect(request.META.get("HTTP_REFERER") or reverse("pages:landing"))

        if code in dict(settings.LANGUAGES):
            if request.user.is_authenticated:
                user = cast("User", request.user)
                user.language = code
                user.save(update_fields=["language", "updated_at"])
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, code)

        return response
