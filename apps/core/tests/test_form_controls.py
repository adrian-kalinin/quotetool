from django import forms
from django.test import SimpleTestCase

from apps.core.templatetags.form_controls import control_class


class ControlClassTests(SimpleTestCase):
    """Tests for the control_class template filter."""

    def test_checkbox_widget_gets_form_check_input(self) -> None:
        class Form(forms.Form):
            accept = forms.BooleanField()

        self.assertEqual(control_class(Form()["accept"]), "form-check-input")

    def test_select_widget_gets_form_select(self) -> None:
        class Form(forms.Form):
            choice = forms.ChoiceField(choices=[("a", "A")])

        self.assertEqual(control_class(Form()["choice"]), "form-select")

    def test_other_widgets_get_form_control(self) -> None:
        class Form(forms.Form):
            name = forms.CharField()

        self.assertEqual(control_class(Form()["name"]), "form-control")
