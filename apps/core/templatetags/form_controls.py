from django import forms
from django import template

register = template.Library()


@register.filter
def control_class(field: forms.BoundField) -> str:
    """Return the Tabler form control CSS class for a bound field's widget."""
    widget = field.field.widget

    if isinstance(widget, forms.CheckboxInput):
        return "form-check-input"

    if isinstance(widget, forms.Select):
        return "form-select"

    return "form-control"
