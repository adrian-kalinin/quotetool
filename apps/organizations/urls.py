from django.urls import path

from apps.organizations import views

app_name = "organizations"

urlpatterns = [
    path("onboarding/", views.OnboardingView.as_view(), name="onboarding"),
    path("organizations/new/", views.OrganizationCreateView.as_view(), name="organization-create"),
    path("organizations/switch/<uuid:org_uuid>/", views.OrganizationSwitchView.as_view(), name="organization-switch"),
    path("organizations/leave/", views.OrganizationLeaveView.as_view(), name="organization-leave"),
    path("settings/", views.SettingsOrganizationView.as_view(), name="settings-organization"),
    path(
        "settings/organization/details/",
        views.OrganizationUpdateView.as_view(),
        name="settings-organization-details",
    ),
    path("settings/organization/invite/", views.MemberInviteView.as_view(), name="settings-member-invite"),
    path(
        "settings/organization/invitations/<int:invitation_id>/resend/",
        views.InvitationResendView.as_view(),
        name="settings-invitation-resend",
    ),
    path(
        "settings/organization/invitations/<int:invitation_id>/revoke/",
        views.InvitationRevokeView.as_view(),
        name="settings-invitation-revoke",
    ),
    path(
        "settings/organization/members/<int:membership_id>/role/",
        views.MemberRoleUpdateView.as_view(),
        name="settings-member-role",
    ),
    path(
        "settings/organization/members/<int:membership_id>/remove/",
        views.MemberRemoveView.as_view(),
        name="settings-member-remove",
    ),
    path(
        "settings/organization/members/<int:membership_id>/transfer-ownership/",
        views.MemberTransferOwnershipView.as_view(),
        name="settings-member-transfer-ownership",
    ),
    path("invitations/", views.InvitationListView.as_view(), name="invitations"),
    path("invitations/<int:invitation_id>/accept/", views.InvitationAcceptView.as_view(), name="invitation-accept"),
    path("invitations/<int:invitation_id>/decline/", views.InvitationDeclineView.as_view(), name="invitation-decline"),
]
