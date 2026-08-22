from django import forms

from apps.organizations.models import Organization
from apps.organizations.models import OrganizationInvitation


class OrganizationForm(forms.ModelForm):
    name = forms.CharField(
        label="Organization name",
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Acme Inc."}),
    )

    class Meta:
        model = Organization
        fields = ("name",)


class InviteMemberForm(forms.ModelForm):
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={"placeholder": "john.doe@example.com"}),
    )

    class Meta:
        model = OrganizationInvitation
        fields = ("email",)
