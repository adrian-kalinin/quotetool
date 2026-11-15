from collections.abc import Callable
from urllib.parse import unquote
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.middleware.locale import LocaleMiddleware
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
