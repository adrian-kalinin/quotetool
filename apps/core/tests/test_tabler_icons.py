from django.test import SimpleTestCase

from apps.core.templatetags.tabler_icons import tabler_icon


class TablerIconTests(SimpleTestCase):
    """Tests for the tabler_icon template tag."""

    def test_renders_inline_svg_without_xmlns(self) -> None:
        svg = tabler_icon("mail")

        self.assertTrue(svg.startswith("<svg"))
        self.assertNotIn("xmlns", svg)
        self.assertNotIn("ns0:", svg)

    def test_size_overrides_width_and_height(self) -> None:
        svg = tabler_icon("mail", size=32)

        self.assertIn('width="32"', svg)
        self.assertIn('height="32"', svg)

    def test_extra_class_is_appended_to_existing_classes(self) -> None:
        svg = tabler_icon("mail", extra_class="text-danger")

        self.assertIn("icon-tabler-mail", svg)
        self.assertIn("text-danger", svg)

    def test_missing_icon_renders_html_comment(self) -> None:
        result = tabler_icon("this-icon-does-not-exist")

        self.assertEqual(result, "<!-- Icon this-icon-does-not-exist (outline) not found -->")
