from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase
from django.test import override_settings

from apps.billing.checks import check_polar_product_mapping
from apps.billing.plans import PlanKey


class CheckPolarProductMappingTests(SimpleTestCase):
    """Tests for the boot-time POLAR_PRODUCT_IDS system check."""

    def test_valid_mapping_passes(self) -> None:
        with override_settings(POLAR_PRODUCT_IDS={PlanKey.STARTER: "prod-a"}):
            errors = check_polar_product_mapping(None)
        self.assertEqual(errors, [])

    def test_empty_mapping_passes(self) -> None:
        with override_settings(POLAR_PRODUCT_IDS={}):
            errors = check_polar_product_mapping(None)
        self.assertEqual(errors, [])

    def test_undefined_setting_fails(self) -> None:
        with mock.patch("apps.billing.checks.settings", SimpleNamespace()):
            errors = check_polar_product_mapping(None)
        self.assertEqual([error.id for error in errors], ["billing.E001"])

    def test_unknown_plan_key_fails(self) -> None:
        with override_settings(POLAR_PRODUCT_IDS={"retired": "prod-a"}):
            errors = check_polar_product_mapping(None)
        self.assertEqual([error.id for error in errors], ["billing.E002"])

    def test_empty_product_id_fails(self) -> None:
        with override_settings(POLAR_PRODUCT_IDS={PlanKey.STARTER: ""}):
            errors = check_polar_product_mapping(None)
        self.assertEqual([error.id for error in errors], ["billing.E003"])

    def test_duplicate_product_id_fails(self) -> None:
        plans = {PlanKey.STARTER: object(), "other": object()}
        mapping = {PlanKey.STARTER: "prod-a", "other": "prod-a"}

        with mock.patch("apps.billing.checks.BILLING_PLANS", plans), override_settings(POLAR_PRODUCT_IDS=mapping):
            errors = check_polar_product_mapping(None)

        self.assertIn("billing.E004", [error.id for error in errors])
