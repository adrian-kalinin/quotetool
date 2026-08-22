from django import forms

from apps.accounts.models import User


class ProfileForm(forms.ModelForm):
    name = forms.CharField(
        label="Name",
        widget=forms.TextInput(attrs={"placeholder": "Enter your name"}),
    )

    class Meta:
        model = User
        fields = ("name",)
