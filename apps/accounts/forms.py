from django import forms
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User


class ProfileForm(forms.ModelForm):
    name = forms.CharField(
        label=_("Name"),
        widget=forms.TextInput(attrs={"placeholder": _("Enter your name")}),
    )

    class Meta:
        model = User
        fields = ("name",)
