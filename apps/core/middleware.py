from collections.abc import Callable
from functools import cache
from urllib.parse import unquote
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.middleware.locale import LocaleMiddleware
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils import translation
from django_htmx.http import trigger_client_event

from apps.core.http import HttpRequest


class HtmxMessagesMiddleware:
    """Trigger a `fetch-messages` client event when messages are queued, so toasts appear."""

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        storage = messages.get_messages(request)

        if len(storage) > 0:
            response = trigger_client_event(response, "fetch-messages", after="settle")

        return response


class HtmxOnlyMiddleware:
    """Redirect non-htmx requests on htmx-only endpoints to their parent page."""

    _PROTECTED_PAGES = {
        "account_change_password": "accounts:settings-security",
        "account_set_password": "accounts:settings-security",
        "account_email": "accounts:settings-account",
        "socialaccount_connections": "accounts:settings-account",
        "core:hx-messages": "dashboard:dashboard",
    }

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        redirect_to = self._protected_paths().get(request.path)

        if redirect_to is not None and not request.htmx:
            return redirect(redirect_to)

        return self.get_response(request)

    @classmethod
    @cache
    def _protected_paths(cls) -> dict[str, str]:
        """Map htmx-only paths to the page they belong to."""
        return {reverse(name): reverse(to) for name, to in cls._PROTECTED_PAGES.items()}


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


class UserTimezoneMiddleware:
    """Activate the timezone stored in the django_timezone cookie (falling back to UTC)."""

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        tz = self._resolve(request)

        if tz is not None:
            timezone.activate(tz)
        else:
            timezone.deactivate()

        return self.get_response(request)

    @staticmethod
    def _resolve(request: HttpRequest) -> ZoneInfo | None:
        name = unquote(request.COOKIES.get(settings.TIMEZONE_COOKIE_NAME, ""))

        try:
            return ZoneInfo(name) if name else None
        except (ZoneInfoNotFoundError, ValueError):
            return None
