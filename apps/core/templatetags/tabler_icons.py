import functools
from copy import deepcopy
from xml.etree import ElementTree as ET

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()


class IconDoesNotExistError(Exception):
    """Raised when a tabler icon SVG file is missing."""


@functools.lru_cache(maxsize=256)
def _load_icon(style: str, name: str) -> ET.Element:
    """Load an icon SVG from disk and strip its namespace prefix."""
    icon_path = settings.BASE_DIR / "static" / "libs" / "tabler" / "icons" / style / f"{name}.svg"

    try:
        svg_bytes = icon_path.read_bytes()
    except FileNotFoundError as err:
        raise IconDoesNotExistError from err

    svg = ET.fromstring(svg_bytes.decode())  # noqa: S314

    # Remove namespace prefix to prevent 'ns0:' in output
    for node in svg.iter():
        node.tag = node.tag.removeprefix("{http://www.w3.org/2000/svg}")

    return svg


def _render_icon(style: str, name: str, size: int | None, extra_class: str | None) -> str:
    """Render an icon to an SVG string with optional size and extra CSS class."""
    svg = deepcopy(_load_icon(style, name))

    if size is not None:
        svg.attrib["width"] = svg.attrib["height"] = str(size)

    if extra_class:
        existing_class = svg.attrib.get("class", "")
        svg.attrib["class"] = f"{existing_class} {extra_class}".strip()

    string = ET.tostring(svg, encoding="unicode")

    # Inline SVGs don't need xmlns
    return string.replace(' xmlns="http://www.w3.org/2000/svg"', "", 1)


@register.simple_tag
def tabler_icon(name: str, style: str = "outline", size: int | None = None, extra_class: str = "") -> str:
    """Render a Tabler icon as inline SVG, or an HTML comment if missing."""
    try:
        svg_string = _render_icon(style, name, size, extra_class)
        return mark_safe(svg_string)  # noqa: S308
    except IconDoesNotExistError:
        return mark_safe(f"<!-- Icon {name} ({style}) not found -->")  # noqa: S308
