from functools import lru_cache

from django.conf import settings
from polar.v2026_04 import Polar


@lru_cache(maxsize=1)
def get_polar_client() -> Polar:
    return Polar(settings.POLAR_ACCESS_TOKEN, environment="sandbox" if settings.POLAR_SANDBOX else "production")
