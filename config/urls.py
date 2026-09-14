from django.conf import settings
from django.contrib import admin
from django.urls import include
from django.urls import path

urlpatterns = [
    path("", include("apps.pages.urls")),
    path("app/", include("apps.core.urls")),
    path("app/", include("apps.authn.urls")),
    path("app/", include("apps.accounts.urls")),
    path("app/", include("apps.organizations.urls")),
    path("app/", include("apps.customers.urls")),
    path("app/", include("apps.billing.urls")),
    path("app/", include("apps.dashboard.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]
