from django.test import TestCase
from django.utils import translation

from apps.customers.forms import country_names


class CountryNamesTests(TestCase):
    """Tests for the country name suggestions."""

    def test_names_are_localized_to_the_active_language(self) -> None:
        with translation.override("en-gb"):
            self.assertIn("Germany", country_names())

        with translation.override("de-de"):
            self.assertIn("Deutschland", country_names())

    def test_excludes_non_country_territories(self) -> None:
        with translation.override("en-gb"):
            names = country_names()

        self.assertNotIn("European Union", names)
        self.assertNotIn("World", names)
