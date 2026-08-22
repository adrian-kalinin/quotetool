from dataclasses import dataclass

from django.conf import settings
from django.db import models


class PlanKey(models.TextChoices):
    STARTER = "starter", "Starter"


@dataclass(frozen=True)
class Plan:
    key: PlanKey
    name: str
    tagline: str
    perks: tuple[str, ...]
    highlight: bool = False
    badge: str = ""
    public: bool = True


BILLING_PLANS: dict[PlanKey, Plan] = {
    PlanKey.STARTER: Plan(
        key=PlanKey.STARTER,
        name="Starter",
        tagline="Perfect for individuals and small businesses.",
        perks=(
            "Up to 10 users",
            "Unlimited projects",
            "Advanced analytics",
            "7-day free trial",
            "Priority support",
        ),
        highlight=True,
        badge="Most popular",
    ),
}


def product_id_for(plan_key: PlanKey) -> str | None:
    """Return the plan's current Polar product id, or None if the plan is not on sale."""
    return settings.POLAR_PRODUCT_IDS.get(plan_key)


def resolve_plan(product_id: str) -> PlanKey | None:
    """Reverse lookup: Polar product id -> PlanKey, or None if unmapped."""
    for plan_key, mapped_id in settings.POLAR_PRODUCT_IDS.items():
        if mapped_id == product_id:
            return plan_key
    return None
