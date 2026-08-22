from django.urls import path

from apps.billing import views

app_name = "billing"

urlpatterns = [
    path("settings/billing/", views.BillingSettingsView.as_view(), name="settings-billing"),
    path("settings/billing/checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("settings/billing/checkout/success/", views.CheckoutSuccessView.as_view(), name="checkout-success"),
    path("settings/billing/portal/", views.PortalRedirectView.as_view(), name="portal"),
    path("billing/webhook/", views.WebhookView.as_view(), name="webhook"),
]
