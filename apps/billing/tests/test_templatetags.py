from django.test import SimpleTestCase
from django.utils import translation

from apps.billing.templatetags.billing import money


class MoneyFilterTests(SimpleTestCase):
    """Tests for the money template filter."""

    def test_none_amount_returns_empty_string(self) -> None:
        self.assertEqual(money(None, "usd"), "")
        self.assertEqual(money(None, None), "")

    def test_amount_with_currency_formats_cents_and_uppercases_currency(self) -> None:
        with translation.override("en-us"):
            self.assertEqual(money(2905, "usd"), "$29.05")

    def test_amount_without_currency_formats_plain_number(self) -> None:
        with translation.override("en-us"):
            self.assertEqual(money(2900, None), "29")

    def test_formatting_follows_active_language(self) -> None:
        with translation.override("fr-fr"):
            self.assertEqual(money(2900, "eur"), "29,00\xa0€")
