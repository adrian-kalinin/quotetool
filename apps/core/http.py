from django.http import HttpRequest as BaseHttpRequest
from django_htmx.middleware import HtmxDetails

from apps.accounts.models import User


class HttpRequest(BaseHttpRequest):
    htmx: HtmxDetails


class AuthenticatedHttpRequest(HttpRequest):
    user: User
