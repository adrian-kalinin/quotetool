from django.contrib import messages
from django.views.generic.base import TemplateView


class MessagesView(TemplateView):
    """Render queued Django messages as toast markup (fetched by htmx)."""

    template_name = "snippets/messages.html"

    def get_context_data(self, **kwargs) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["messages"] = messages.get_messages(self.request)
        return context
