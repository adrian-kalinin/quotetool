from decimal import Decimal

from babel.numbers import format_currency
from babel.numbers import format_number
from django import template
from django.utils.translation import get_language
from django.utils.translation import to_locale

register = template.Library()


@register.filter
def money(amount: int | None, currency: str | None) -> str:
    if amount is None:
        return ""

    locale = to_locale(get_language())

    if currency is not None:
        return format_currency(Decimal(amount) / 100, currency.upper(), locale=locale)

    return format_number(Decimal(amount) / 100, locale=locale)
