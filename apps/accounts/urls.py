from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("settings/account/", views.SettingsAccountView.as_view(), name="settings-account"),
    path("settings/account/profile/", views.ProfileUpdateView.as_view(), name="settings-profile"),
    path("settings/security/", views.SettingsSecurityView.as_view(), name="settings-security"),
]
