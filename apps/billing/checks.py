from collections.abc import Sequence

from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Error
from django.core.checks import register

from apps.billing.plans import BILLING_PLANS


@register()
def check_polar_product_mapping(app_configs: Sequence[AppConfig] | None, **kwargs) -> list[Error]:  # noqa: ARG001
    """Boot-time validation of settings.POLAR_PRODUCT_IDS against the plan catalog."""
    errors = []

    if not hasattr(settings, "POLAR_PRODUCT_IDS"):
        errors.append(
            Error("POLAR_PRODUCT_IDS is not defined; every settings module must define it.", id="billing.E001")
        )
        return errors

    seen = set()

    for plan_key, product_id in settings.POLAR_PRODUCT_IDS.items():
        if plan_key not in BILLING_PLANS:
            errors.append(Error(f"POLAR_PRODUCT_IDS references unknown plan key '{plan_key!r}'.", id="billing.E002"))
            continue
        if not product_id:
            errors.append(
                Error(f"Plan '{plan_key.value!r}' has an empty product ID. Omit the plan instead.", id="billing.E003")
            )
            continue
        if product_id in seen:
            errors.append(
                Error(f"Product ID '{product_id!r}' is used more than once in POLAR_PRODUCT_IDS.", id="billing.E004")
            )
        seen.add(product_id)

    return errors
