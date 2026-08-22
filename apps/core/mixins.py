from typing import TYPE_CHECKING

from django.contrib.auth.mixins import LoginRequiredMixin as BaseLoginRequiredMixin

if TYPE_CHECKING:
    from apps.core.http import AuthenticatedHttpRequest


class LoginRequiredMixin(BaseLoginRequiredMixin):
    if TYPE_CHECKING:
        request: AuthenticatedHttpRequest
