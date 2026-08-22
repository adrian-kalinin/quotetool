# ruff: noqa: F403, F405
from apps.billing.plans import PlanKey
from config.settings.base import *

INSTALLED_APPS += [
    "django_browser_reload",
]

MIDDLEWARE += [
    "django_browser_reload.middleware.BrowserReloadMiddleware",
]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

POLAR_PRODUCT_IDS = {
    PlanKey.STARTER: "cf99a43a-117e-4aa5-84c3-5ef470230c5a",
}
