from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from apps.billing.client import get_polar_client


class Command(BaseCommand):
    """Live-validate every configured Polar product ID."""

    help = "Validate that every Polar product in POLAR_PRODUCT_IDS exists, is not archived, and is monthly."

    def handle(self, *args: object, **options: object) -> None:  # noqa: ARG002
        client = get_polar_client()
        failures: list[str] = []
        checked = 0

        for plan_key, product_id in settings.POLAR_PRODUCT_IDS.items():
            if not product_id:
                continue

            checked += 1

            try:
                product = client.products.get(id=product_id)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{plan_key.value} ({product_id}): fetch failed ({exc})")
                continue

            if product.is_archived:
                failures.append(f"{plan_key.value} ({product_id}): product is archived")

            if product.recurring_interval != "month" or product.recurring_interval_count != 1:
                failures.append(
                    f"{plan_key.value} ({product_id}): recurring interval "
                    f"is {product.recurring_interval_count!r} {product.recurring_interval!r}, "
                    f"expected 1 'month'"
                )

        if failures:
            raise CommandError("Polar product check failed:\n" + "\n".join(failures))

        self.stdout.write(self.style.SUCCESS(f"OK: {checked} Polar product(s) valid."))
