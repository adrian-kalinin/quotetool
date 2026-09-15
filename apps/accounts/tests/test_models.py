from django.db import IntegrityError
from django.db import transaction
from django.test import TestCase

from apps.accounts.models import User


class UserManagerTests(TestCase):
    """Tests for the custom email-based user manager."""

    def test_create_user_normalizes_email_domain(self) -> None:
        user = User.objects.create_user("Alice@EXAMPLE.com", "testpass123")

        self.assertEqual(user.email, "Alice@example.com")

    def test_create_user_sets_safe_defaults(self) -> None:
        user = User.objects.create_user("user@example.com", "testpass123")

        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.has_usable_password())

    def test_create_user_without_password_creates_unusable_password(self) -> None:
        user = User.objects.create_user("user@example.com")

        self.assertFalse(user.has_usable_password())

    def test_create_user_without_email_raises(self) -> None:
        with self.assertRaisesMessage(ValueError, "User must have an email address"):
            User.objects.create_user("", "testpass123")

    def test_create_superuser_sets_admin_flags(self) -> None:
        user = User.objects.create_superuser("admin@example.com", "testpass123")

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_create_superuser_rejects_is_staff_false(self) -> None:
        with self.assertRaisesMessage(ValueError, "Superuser must have is_staff=True"):
            User.objects.create_superuser("admin@example.com", "testpass123", is_staff=False)

    def test_create_superuser_rejects_is_superuser_false(self) -> None:
        with self.assertRaisesMessage(ValueError, "Superuser must have is_superuser=True"):
            User.objects.create_superuser("admin@example.com", "testpass123", is_superuser=False)

    def test_email_must_be_unique(self) -> None:
        User.objects.create_user("dupe@example.com", "testpass123")

        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("dupe@example.com", "testpass123")


class UserDisplayNameTests(TestCase):
    """Tests for User.display_name."""

    def test_returns_name_when_set(self) -> None:
        user = User.objects.create_user("user@example.com", name="Ada Lovelace")

        self.assertEqual(user.display_name, "Ada Lovelace")

    def test_falls_back_to_email_without_name(self) -> None:
        user = User.objects.create_user("user@example.com")

        self.assertEqual(user.display_name, "user@example.com")
