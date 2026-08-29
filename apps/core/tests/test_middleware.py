from http import HTTPStatus
from unittest.mock import Mock

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpRequest
from django.http import HttpResponse
from django.test import RequestFactory
from django.test import SimpleTestCase
from django.urls import reverse
from django_htmx.middleware import HtmxDetails

from apps.accounts.models import User
from apps.core.middleware import UserLocaleMiddleware
from apps.core.middleware import htmx_messages_middleware
from apps.core.middleware import htmx_only_middleware


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
        request = self._request(language="de", cookie="en", header="en")
        self.assertEqual(self._resolved_language(request), "de")

    def test_cookie_beats_header(self) -> None:
        request = self._request(cookie="de", header="en")
        self.assertEqual(self._resolved_language(request), "de")

    def test_header_is_used_as_fallback(self) -> None:
        request = self._request(header="de")
        self.assertEqual(self._resolved_language(request), "de")

    def test_user_without_language_falls_through_to_cookie(self) -> None:
        request = self._request(cookie="de", header="en")
        self.assertEqual(self._resolved_language(request), "de")

    def test_default_language_is_english(self) -> None:
        request = self._request(header="fr")
        self.assertEqual(self._resolved_language(request), "en")


class HtmxOnlyMiddlewareTests(SimpleTestCase):
    """Non-htmx requests to htmx-only endpoints are redirected to the parent page."""

    def _call(self, path: str, *, htmx: bool) -> HttpResponse:
        get_response = Mock(return_value=HttpResponse("ok"))
        middleware = htmx_only_middleware(get_response)
        request = RequestFactory().get(path)

        if htmx:
            request.META["HTTP_HX_REQUEST"] = "true"

        request.htmx = HtmxDetails(request)  # type: ignore[reportAttributeAccessIssue]
        return middleware(request)

    def test_non_htmx_request_to_messages_endpoint_redirects(self) -> None:
        response = self._call(reverse("core:hx-messages"), htmx=False)

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("dashboard:dashboard"))

    def test_htmx_request_to_messages_endpoint_passes_through(self) -> None:
        response = self._call(reverse("core:hx-messages"), htmx=True)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.content, b"ok")

    def test_regular_page_is_not_affected(self) -> None:
        response = self._call("/some/regular/page/", htmx=False)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.content, b"ok")


class HtmxMessagesMiddlewareTests(SimpleTestCase):
    """Queued messages add a fetch-messages client event header to the response."""

    def _call(self, *, with_message: bool) -> HttpResponse:
        get_response = Mock(return_value=HttpResponse("ok"))
        middleware = htmx_messages_middleware(get_response)
        request = RequestFactory().get("/")
        request.session = SessionStore()
        request._messages = FallbackStorage(request)  # noqa: SLF001  # type: ignore[reportAttributeAccessIssue]

        if with_message:
            messages.add_message(request, messages.ERROR, "test error")

        return middleware(request)

    def test_event_header_is_set_when_messages_are_queued(self) -> None:
        response = self._call(with_message=True)

        self.assertIn("fetch-messages", response.headers.get("HX-Trigger-After-Settle", ""))

    def test_no_event_header_without_messages(self) -> None:
        response = self._call(with_message=False)

        self.assertNotIn("HX-Trigger-After-Settle", response.headers)
