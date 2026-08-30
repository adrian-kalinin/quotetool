from unittest.mock import Mock

from allauth.socialaccount.models import SocialLogin
from django.conf import settings
from django.test import RequestFactory
from django.test import TestCase

from apps.accounts.models import User
from apps.authn.adapters import SocialAccountAdapter


class SocialAccountAdapterTests(TestCase):
    """Tests for SocialAccountAdapter.populate_user name handling."""

    def setUp(self) -> None:
        self.adapter = SocialAccountAdapter()
        self.request = RequestFactory().get("/")

    def populate(self, data: dict) -> User:
        sociallogin = Mock(spec=SocialLogin)
        sociallogin.user = User(email=data.get("email", ""))
        return self.adapter.populate_user(self.request, sociallogin, data)  # type: ignore[reportArgumentType]

    def test_populates_name_from_first_and_last_name(self) -> None:
        user = self.populate({"first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com"})

        self.assertEqual(user.name, "Ada Lovelace")

    def test_populates_name_from_first_name_only(self) -> None:
        user = self.populate({"first_name": "Ada", "email": "ada@example.com"})

        self.assertEqual(user.name, "Ada")

    def test_populates_empty_name_without_provider_names(self) -> None:
        user = self.populate({"email": "ada@example.com"})

        self.assertEqual(user.name, "")

    def test_populates_language_from_cookie(self) -> None:
        self.request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = "de"
        user = self.populate({"first_name": "Ada", "email": "ada@example.com"})

        self.assertEqual(user.language, "de")

    def test_ignores_invalid_language_cookie(self) -> None:
        self.request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = "xx"
        user = self.populate({"first_name": "Ada", "email": "ada@example.com"})

        self.assertEqual(user.language, "en")
