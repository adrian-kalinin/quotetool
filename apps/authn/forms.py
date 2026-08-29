from typing import cast

import allauth.account.forms as allauth_forms
from django import forms
from django.http import HttpRequest
from django.utils.functional import _StrPromise
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User


def update_field(
    field: forms.Field,
    *,
    label: str | _StrPromise | None = None,
    help_text: str | _StrPromise | None = None,
    placeholder: str | _StrPromise | None = None,
    icon: str | None = None,
) -> None:
    """Apply label, help text, placeholder, and icon overrides to a form field."""
    if label is not None:
        field.label = label
    if help_text is not None:
        field.help_text = help_text
    if placeholder is not None:
        field.widget.attrs.update({"placeholder": placeholder})
    if icon is not None:
        field.icon = icon  # type: ignore[reportAttributeAccessIssue]


class LoginForm(allauth_forms.LoginForm):
    """Login form with placeholder and icon styling."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        update_field(self.fields["login"], placeholder=_("Enter your email"), icon="mail")
        update_field(self.fields["password"], placeholder=_("Enter your password"), icon="lock")
        update_field(self.fields["remember"], label=_("Remember me"))


class SignupForm(allauth_forms.SignupForm):
    """Signup form collecting the user's name alongside email and password."""

    name = forms.CharField(
        max_length=50,
        required=True,
        label=_("Name"),
        widget=forms.TextInput(attrs={"placeholder": _("Enter your name")}),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        update_field(self.fields["name"], icon="user")
        update_field(self.fields["email"], placeholder=_("Enter your email"), icon="mail")
        update_field(self.fields["password1"], help_text="", placeholder=_("Enter your password"), icon="lock")

    def save(self, request: HttpRequest) -> User:
        user = cast("User", super().save(request))
        user.name = self.cleaned_data.get("name", "").strip()
        user.save(update_fields=["name"])
        return user


class ChangePasswordForm(allauth_forms.ChangePasswordForm):
    """Password change form with cleaned-up labels and placeholders."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        update_field(self.fields["oldpassword"], label=_("Current password"), placeholder=_("Enter current password"))
        update_field(
            self.fields["password1"], label=_("New password"), help_text="", placeholder=_("Enter new password")
        )
        update_field(
            self.fields["password2"],
            label=_("New password (again)"),
            help_text="",
            placeholder=_("Confirm new password"),
        )


class SetPasswordForm(allauth_forms.SetPasswordForm):
    """Password set form for accounts without a usable password (e.g. social signup)."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        update_field(
            self.fields["password1"], label=_("New password"), help_text="", placeholder=_("Enter new password")
        )
        update_field(
            self.fields["password2"],
            label=_("New password (again)"),
            help_text="",
            placeholder=_("Confirm new password"),
        )


class ResetPasswordForm(allauth_forms.ResetPasswordForm):
    """Password reset request form with email placeholder."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        update_field(self.fields["email"], placeholder=_("Enter your email"), icon="mail")


class ResetPasswordKeyForm(allauth_forms.ResetPasswordKeyForm):
    """Password reset confirmation form with the new-password fields."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        update_field(
            self.fields["password1"],
            label=_("New password"),
            help_text="",
            placeholder=_("Enter new password"),
            icon="lock",
        )
        update_field(
            self.fields["password2"],
            label=_("New password (again)"),
            help_text="",
            placeholder=_("Confirm new password"),
            icon="lock",
        )
