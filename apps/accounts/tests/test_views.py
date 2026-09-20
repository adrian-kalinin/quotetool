from http import HTTPStatus

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.organizations.models import OrganizationMembership


def create_member(email: str, *, with_password: bool = True) -> User:
    user = User.objects.create_user(email, "test-password" if with_password else None)
    organization = Organization.objects.create(name="Acme Inc.")
    OrganizationMembership.objects.create(user=user, organization=organization, role=OrganizationMembership.Role.OWNER)
    user.active_organization = organization
    user.save(update_fields=["active_organization"])
    return user


class SettingsAccountViewTests(TestCase):
    """Tests for SettingsAccountView."""

    def test_renders_settings_with_profile_form(self) -> None:
        user = create_member("owner@example.com")
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:settings-account"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "accounts/settings_account.html")
        self.assertEqual(response.context["profile_form"].instance, user)

    def test_renders_timezone_from_cookie(self) -> None:
        user = create_member("owner@example.com")
        self.client.force_login(user)
        self.client.cookies[settings.TIMEZONE_COOKIE_NAME] = "Europe/Berlin"

        response = self.client.get(reverse("accounts:settings-account"))

        self.assertContains(response, "Time zone: <b>Europe/Berlin</b>")
        self.assertContains(response, f"{settings.TIMEZONE_COOKIE_NAME}=")

    def test_anonymous_user_is_redirected_to_login(self) -> None:
        response = self.client.get(reverse("accounts:settings-account"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn(reverse("account_login"), response["Location"])

    def test_user_without_organization_is_sent_to_onboarding(self) -> None:
        user = User.objects.create_user("fresh@example.com", "test-password")
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:settings-account"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("organizations:onboarding"))


class ProfileUpdateViewTests(TestCase):
    """Tests for ProfileUpdateView."""

    def test_post_updates_name_and_redirects(self) -> None:
        user = create_member("owner@example.com")
        self.client.force_login(user)

        response = self.client.post(reverse("accounts:settings-profile"), {"name": "Ada Lovelace", "language": "en"})

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("accounts:settings-account"))

        user.refresh_from_db()
        self.assertEqual(user.name, "Ada Lovelace")

    def test_post_updates_language(self) -> None:
        user = create_member("owner@example.com")
        self.client.force_login(user)

        self.client.post(reverse("accounts:settings-profile"), {"name": "Ada Lovelace", "language": "de"})

        user.refresh_from_db()
        self.assertEqual(user.language, "de")

    def test_htmx_post_renders_profile_partial(self) -> None:
        user = create_member("owner@example.com")
        self.client.force_login(user)

        response = self.client.post(
            reverse("accounts:settings-profile"), {"name": "Ada Lovelace", "language": "en"}, HTTP_HX_REQUEST="true"
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "accounts/partials/settings_profile_details.html")

        user.refresh_from_db()
        self.assertEqual(user.name, "Ada Lovelace")

    def test_htmx_language_change_triggers_full_refresh(self) -> None:
        user = create_member("owner@example.com")
        self.client.force_login(user)

        response = self.client.post(
            reverse("accounts:settings-profile"), {"name": "Ada Lovelace", "language": "de"}, HTTP_HX_REQUEST="true"
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.headers["HX-Refresh"], "true")

        user.refresh_from_db()
        self.assertEqual(user.language, "de")

    def test_blank_name_shows_form_errors(self) -> None:
        user = create_member("owner@example.com")
        user.name = "Ada Lovelace"
        user.save(update_fields=["name"])
        self.client.force_login(user)

        response = self.client.post(reverse("accounts:settings-profile"), {"name": "", "language": "en"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("name", response.context["profile_form"].errors)

        user.refresh_from_db()
        self.assertEqual(user.name, "Ada Lovelace")

    def test_get_is_not_allowed(self) -> None:
        user = create_member("owner@example.com")
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:settings-profile"))

        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)

    def test_anonymous_user_is_redirected_to_login(self) -> None:
        response = self.client.post(reverse("accounts:settings-profile"), {"name": "Ada Lovelace", "language": "en"})

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn(reverse("account_login"), response["Location"])


class SettingsSecurityViewTests(TestCase):
    """Tests for SettingsSecurityView."""

    def test_user_with_usable_password_gets_change_password_form(self) -> None:
        user = create_member("owner@example.com")
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:settings-security"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.context["password_template"], "account/password_change.html")

    def test_user_without_usable_password_gets_set_password_form(self) -> None:
        user = create_member("social@example.com", with_password=False)
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:settings-security"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.context["password_template"], "account/password_set.html")
