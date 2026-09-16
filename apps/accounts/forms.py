from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User


class ProfileForm(forms.ModelForm):
    name = forms.CharField(
        label=_("Name"),
        max_length=50,
        widget=forms.TextInput(attrs={"placeholder": _("Enter your name")}),
    )
    language = forms.ChoiceField(
        label=_("Language"),
        choices=settings.LANGUAGES,
        widget=forms.Select(attrs={"autocomplete": "off"}),
    )

    class Meta:
        model = User
        fields = ("name", "language")
