from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin

from apps.accounts.models import User
from apps.core.http import HttpRequest


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Fill the user's name from the social provider's first/last name."""

    def populate_user(self, request: HttpRequest, sociallogin: SocialLogin, data: dict) -> User:
        user = super().populate_user(request, sociallogin, data)

        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        user.name = f"{first_name} {last_name}".strip()

        return user
