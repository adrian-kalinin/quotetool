from collections.abc import Callable

from django.contrib import messages
from django.http import HttpResponse
from django.middleware.locale import LocaleMiddleware
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import translation
from django_htmx.http import trigger_client_event

from apps.core.http import HttpRequest


def htmx_messages_middleware(get_response: Callable) -> Callable:
    """Trigger a `fetch-messages` client event when messages are queued, so toasts appear."""

    def middleware(request: HttpRequest) -> HttpResponse:
        response = get_response(request)
        storage = messages.get_messages(request)

        if len(storage) > 0:
            response = trigger_client_event(response, "fetch-messages", after="settle")

        return response

    return middleware


def _protected_paths() -> dict[str, str]:
    """Return a map of htmx-only paths to the page they belong to."""
    url_names = {
        "account_change_password": "accounts:settings-security",
        "account_set_password": "accounts:settings-security",
        "account_email": "accounts:settings-account",
        "socialaccount_connections": "accounts:settings-account",
        "core:hx-messages": "dashboard:dashboard",
    }
    return {reverse(url_name): redirect_to for url_name, redirect_to in url_names.items()}


def htmx_only_middleware(get_response: Callable) -> Callable:
    """Redirect non-htmx requests on htmx-only endpoints to their parent page."""

    def middleware(request: HttpRequest) -> HttpResponse:
        redirect_to = _protected_paths().get(request.path)

        if redirect_to is not None and not request.htmx:
            return redirect(redirect_to)

        return get_response(request)

    return middleware


class UserLocaleMiddleware(LocaleMiddleware):
    """LocaleMiddleware that prefers the authenticated user's language (user → cookie → header → default)."""

    def process_request(self, request: HttpRequest) -> None:
        user = getattr(request, "user", None)

        if user is not None and user.is_authenticated:
            language = getattr(user, "language", "")

            if language:
                translation.activate(language)
                request.LANGUAGE_CODE = translation.get_language()
                return

        super().process_request(request)
