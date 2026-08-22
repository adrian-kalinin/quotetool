from django.test import SimpleTestCase
from django.test import override_settings

from apps.billing.plans import PlanKey
from apps.billing.plans import product_id_for
from apps.billing.plans import resolve_plan


class PlanCatalogTests(SimpleTestCase):
    """Tests for the plan catalog's forward and reverse lookups."""

    def test_product_id_for_returns_mapped_product(self) -> None:
        self.assertEqual(product_id_for(PlanKey.STARTER), "test-starter-id")

    def test_product_id_for_returns_none_when_unmapped(self) -> None:
        with override_settings(POLAR_PRODUCT_IDS={}):
            self.assertIsNone(product_id_for(PlanKey.STARTER))

    def test_resolve_plan_reverse_lookup(self) -> None:
        self.assertEqual(resolve_plan("test-starter-id"), PlanKey.STARTER)

    def test_resolve_plan_returns_none_for_unknown_product(self) -> None:
        self.assertIsNone(resolve_plan("prod-unknown"))

    def test_resolve_plan_reflects_changed_settings(self) -> None:
        with override_settings(POLAR_PRODUCT_IDS={PlanKey.STARTER: "prod-other"}):
            self.assertEqual(resolve_plan("prod-other"), PlanKey.STARTER)
            self.assertIsNone(resolve_plan("test-starter-id"))
