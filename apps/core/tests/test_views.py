from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User


class SetLanguageViewTests(TestCase):
    """The language switcher saves to the user model or the django_language cookie."""

    def test_anonymous_request_sets_cookie(self) -> None:
        response = self.client.post(reverse("core:set-language"), {"language": "de-de"}, HTTP_REFERER="/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "de-de")

    def test_authenticated_request_saves_to_user_model(self) -> None:
        user = User.objects.create_user("owner@example.com", "test-password")
        self.client.force_login(user)

        self.client.post(reverse("core:set-language"), {"language": "de-de"})

        user.refresh_from_db()
        self.assertEqual(user.language, "de-de")

    def test_invalid_language_is_rejected(self) -> None:
        response = self.client.post(reverse("core:set-language"), {"language": "xx"}, HTTP_REFERER="/app/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/app/")
        self.assertNotIn(settings.LANGUAGE_COOKIE_NAME, response.cookies)

    def test_redirects_back_to_the_referer(self) -> None:
        response = self.client.post(
            reverse("core:set-language"), {"language": "de-de"}, HTTP_REFERER="/app/settings/account/"
        )

        self.assertEqual(response["Location"], "/app/settings/account/")
