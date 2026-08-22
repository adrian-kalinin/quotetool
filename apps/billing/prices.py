import logging
from dataclasses import dataclass
from typing import cast

from django.conf import settings
from django.core.cache import cache
from polar.v2026_04.outputs import Product
from polar.v2026_04.outputs import ProductPriceFixed

from apps.billing.client import get_polar_client
from apps.billing.plans import BILLING_PLANS
from apps.billing.plans import PlanKey
from apps.billing.plans import product_id_for

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlanPrice:
    amount_cents: int
    currency: str


def get_plan_price(plan_key: PlanKey) -> PlanPrice | None:
    """Live price for a plan, cached with a stale fallback tier.

    Returns None when the plan is not sellable, the API is down with no stale copy,
    or the product has no fixed price - pages render price-less, never 500.
    """
    product_id = product_id_for(plan_key)
    if product_id is None:
        return None

    fresh_key = f"billing:price:{product_id}"
    stale_key = f"billing:price-stale:{product_id}"

    fresh = cache.get(fresh_key)
    if fresh is not None:
        return fresh

    try:
        product = get_polar_client().products.get(id=product_id)
    except Exception:
        logger.exception("Failed to fetch product from Polar API")
        return cache.get(stale_key)

    price = _get_product_fixed_price(product)
    if price is None:
        return None

    plan_price = PlanPrice(amount_cents=price.price_amount, currency=price.price_currency)
    cache.set(fresh_key, plan_price, timeout=settings.POLAR_PRICE_CACHE_TTL)
    cache.set(stale_key, plan_price, timeout=None)
    return plan_price


def _get_product_fixed_price(product: Product) -> ProductPriceFixed | None:
    for price in product.prices:
        if price.amount_type == "fixed" and not price.is_archived:
            return cast("ProductPriceFixed", price)
    return None


def sellable_plans(*, public_only: bool = True) -> list[dict]:
    """Sellable plans as {"plan", "product_id", "price"} for the billing and landing pages."""
    plans = []

    for plan in BILLING_PLANS.values():
        if public_only and not plan.public:
            continue

        if product_id := product_id_for(plan.key):
            plans.append({"plan": plan, "product_id": product_id, "price": get_plan_price(plan.key)})

    return plans
