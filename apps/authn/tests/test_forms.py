from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory
from django.test import TestCase

from apps.accounts.models import User
from apps.authn.forms import SignupForm


class SignupFormTests(TestCase):
    """Tests for the custom signup form."""

    def test_save_persists_the_users_name(self) -> None:
        form = SignupForm(data={"name": "Ada Lovelace", "email": "ada@example.com", "password1": "x9Kq2mZ8vLp4wR7s"})

        self.assertTrue(form.is_valid(), form.errors)
        request = RequestFactory().post("/")
        request.session = SessionStore()
        user = form.save(request)

        self.assertEqual(user.name, "Ada Lovelace")
        self.assertEqual(User.objects.get(email="ada@example.com").name, "Ada Lovelace")

    def test_save_preserves_language_from_cookie(self) -> None:
        form = SignupForm(data={"name": "Ada Lovelace", "email": "ada@example.com", "password1": "x9Kq2mZ8vLp4wR7s"})

        self.assertTrue(form.is_valid(), form.errors)
        request = RequestFactory().post("/")
        request.session = SessionStore()
        request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = "de"
        user = form.save(request)

        self.assertEqual(user.language, "de")

    def test_save_ignores_invalid_language_cookie(self) -> None:
        form = SignupForm(data={"name": "Ada Lovelace", "email": "ada@example.com", "password1": "x9Kq2mZ8vLp4wR7s"})

        self.assertTrue(form.is_valid(), form.errors)
        request = RequestFactory().post("/")
        request.session = SessionStore()
        request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = "xx"
        user = form.save(request)

        self.assertEqual(user.language, "en")

    def test_name_is_required(self) -> None:
        form = SignupForm(data={"email": "ada@example.com", "password1": "x9Kq2mZ8vLp4wR7s"})

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
