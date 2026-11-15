from unittest.mock import Mock
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpRequest
from django.http import HttpResponse
from django.test import RequestFactory
from django.test import SimpleTestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.core.middleware import HtmxMessagesMiddleware
from apps.core.middleware import UserLocaleMiddleware
from apps.core.middleware import UserTimezoneMiddleware


class UserLocaleMiddlewareTests(SimpleTestCase):
    """Language resolution order: user preference → cookie → Accept-Language → default."""

    def setUp(self) -> None:
        self.middleware = UserLocaleMiddleware(get_response=lambda _request: HttpResponse())

    def _request(self, *, language: str = "", cookie: str = "", header: str = "") -> HttpRequest:
        request = RequestFactory().get("/")
        request.session = SessionStore()
        request.user = User(language=language) if language else AnonymousUser()

        if cookie:
            request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = cookie
        if header:
            request.META["HTTP_ACCEPT_LANGUAGE"] = header

        return request

    def _resolved_language(self, request: HttpRequest) -> str:
        self.middleware.process_request(request)  # type: ignore[reportArgumentType]
        return request.LANGUAGE_CODE

    def test_user_language_beats_cookie_and_header(self) -> None:
        request = self._request(language="de-de", cookie="en-gb", header="en-gb")
        self.assertEqual(self._resolved_language(request), "de-de")

    def test_cookie_beats_header(self) -> None:
        request = self._request(cookie="de-de", header="en-gb")
        self.assertEqual(self._resolved_language(request), "de-de")

    def test_header_is_used_as_fallback(self) -> None:
        request = self._request(header="de-de")
        self.assertEqual(self._resolved_language(request), "de-de")

    def test_user_without_language_falls_through_to_cookie(self) -> None:
        request = self._request(cookie="de-de", header="en-gb")
        self.assertEqual(self._resolved_language(request), "de-de")

    def test_default_language_is_english(self) -> None:
        request = self._request(header="fr")
        self.assertEqual(self._resolved_language(request), "en-gb")


class UserTimezoneMiddlewareTests(SimpleTestCase):
    """Timezone resolution: the django_timezone cookie, falling back to the default."""

    def setUp(self) -> None:
        self.middleware = UserTimezoneMiddleware(get_response=lambda _request: HttpResponse())
        self.addCleanup(timezone.deactivate)

    def _resolved_timezone(self, *, cookie: str = "") -> str:
        request = RequestFactory().get("/")

        if cookie:
            request.COOKIES[settings.TIMEZONE_COOKIE_NAME] = cookie

        self.middleware(request)  # type: ignore[reportArgumentType]
        return timezone.get_current_timezone_name()

    def test_cookie_is_used(self) -> None:
        self.assertEqual(self._resolved_timezone(cookie="Europe/Berlin"), "Europe/Berlin")

    def test_url_encoded_cookie_is_decoded(self) -> None:
        self.assertEqual(self._resolved_timezone(cookie=quote("Europe/Berlin", safe="")), "Europe/Berlin")

    def test_default_timezone_is_utc(self) -> None:
        self.assertEqual(self._resolved_timezone(), settings.TIME_ZONE)

    def test_invalid_cookie_timezone_falls_back_to_utc(self) -> None:
        self.assertEqual(self._resolved_timezone(cookie="Mars/Olympus"), settings.TIME_ZONE)


class HtmxMessagesMiddlewareTests(SimpleTestCase):
    """Queued messages add a fetch-messages client event header to the response."""

    def _call(self, *, with_message: bool) -> HttpResponse:
        get_response = Mock(return_value=HttpResponse("ok"))
        middleware = HtmxMessagesMiddleware(get_response)
        request = RequestFactory().get("/")
        request.session = SessionStore()
        request._messages = FallbackStorage(request)  # noqa: SLF001  # type: ignore[reportAttributeAccessIssue]

        if with_message:
            messages.add_message(request, messages.ERROR, "test error")

        return middleware(request)  # type: ignore[reportArgumentType]

    def test_event_header_is_set_when_messages_are_queued(self) -> None:
        response = self._call(with_message=True)

        self.assertIn("fetch-messages", response.headers.get("HX-Trigger-After-Settle", ""))

    def test_no_event_header_without_messages(self) -> None:
        response = self._call(with_message=False)

        self.assertNotIn("HX-Trigger-After-Settle", response.headers)
