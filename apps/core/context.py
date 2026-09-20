from django.conf import settings
from django.http import HttpRequest


def timezone(_request: HttpRequest) -> dict[str, str]:
    """Expose the timezone cookie name so the browser detection script stays in sync."""
    return {"TIMEZONE_COOKIE_NAME": settings.TIMEZONE_COOKIE_NAME}
