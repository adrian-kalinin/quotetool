from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING
from typing import cast
from uuid import uuid4

from polar.v2026_04.outputs import CustomerStateIndividual
from polar.v2026_04.outputs import CustomerStateSubscription
from polar.v2026_04.outputs import Product
from polar.v2026_04.outputs import ProductPrice
from polar.v2026_04.outputs import ProductPriceCustom
from polar.v2026_04.outputs import ProductPriceFixed
from polar.v2026_04.outputs import Subscription as PolarSubscription
from polar.v2026_04.outputs import SubscriptionCustomer

if TYPE_CHECKING:
    from polar.v2026_04.literals import Status
    from polar.v2026_04.literals import SubscriptionStatus


def make_customer(*, customer_id: str = "cust-1", external_id: str | None = None) -> SubscriptionCustomer:
    return SubscriptionCustomer(
        id=customer_id,
        created_at="2025-01-01T00:00:00Z",
        modified_at=None,
        metadata={},
        external_id=external_id or str(uuid4()),
        email="owner@example.com",
        email_verified=True,
        type="individual",
        name="Acme Inc.",
        billing_name=None,
        billing_address=None,
        tax_id=[],
        locale="en",
        organization_id="org-polar-1",
        default_payment_method_id=None,
        deleted_at=None,
        avatar_url=None,
    )


def make_product(*, product_id: str = "test-starter-id", prices: Sequence[ProductPrice] | None = None) -> Product:
    return Product(
        id=product_id,
        created_at="2025-01-01T00:00:00Z",
        modified_at=None,
        trial_interval=None,
        trial_interval_count=None,
        name="Starter",
        description=None,
        visibility="public",
        recurring_interval="month",
        recurring_interval_count=1,
        meter_interval=None,
        meter_interval_count=None,
        is_recurring=True,
        is_archived=False,
        organization_id="org-polar-1",
        metadata={},
        prices=list(prices or []),
        benefits=[],
        medias=[],
        attached_custom_fields=[],
    )


def _to_iso(value: str | datetime) -> str:
    """Normalize a datetime to the ISO string the Polar dataclasses expect."""
    return value.isoformat() if isinstance(value, datetime) else value


def make_fixed_price(
    *,
    price_id: str = "price-1",
    product_id: str = "test-starter-id",
    amount: int = 2900,
    currency: str = "usd",
    is_archived: bool = False,
) -> ProductPriceFixed:
    """Build a real ProductPriceFixed."""
    return ProductPriceFixed(
        created_at="2025-01-01T00:00:00Z",
        modified_at=None,
        id=price_id,
        source="catalog",
        amount_type="fixed",
        price_currency=currency,
        tax_behavior=None,
        is_archived=is_archived,
        product_id=product_id,
        price_amount=amount,
    )


def make_custom_price(
    *,
    price_id: str = "price-2",
    product_id: str = "test-starter-id",
    currency: str = "usd",
    is_archived: bool = False,
) -> ProductPriceCustom:
    """Build a real ProductPriceCustom."""
    return ProductPriceCustom(
        created_at="2025-01-01T00:00:00Z",
        modified_at=None,
        id=price_id,
        source="catalog",
        amount_type="custom",
        price_currency=currency,
        tax_behavior=None,
        is_archived=is_archived,
        product_id=product_id,
        minimum_amount=100,
        maximum_amount=None,
        preset_amount=None,
    )


def make_subscription(  # noqa: PLR0913
    *,
    subscription_id: str = "sub-1",
    product_id: str = "test-starter-id",
    customer_id: str = "cust-1",
    external_id: str | None = None,
    status: str = "active",
    cancel_at_period_end: bool = False,
    current_period_end: str | datetime = "2025-02-01T00:00:00Z",
    amount: int = 2900,
    currency: str = "usd",
) -> PolarSubscription:
    """Build a real webhook-Subscription-shaped Polar object."""
    return PolarSubscription(
        id=subscription_id,
        created_at="2025-01-01T00:00:00Z",
        modified_at=None,
        amount=amount,
        currency=currency,
        recurring_interval="month",
        recurring_interval_count=1,
        status=cast("SubscriptionStatus", status),
        current_period_start="2025-01-01T00:00:00Z",
        current_period_end=_to_iso(current_period_end),
        current_meter_period_start=None,
        current_meter_period_end=None,
        trial_start=None,
        trial_end=None,
        cancel_at_period_end=cancel_at_period_end,
        canceled_at=None,
        started_at="2025-01-01T00:00:00Z",
        ends_at=None,
        ended_at=None,
        past_due_at=None,
        pause_at_period_end=False,
        paused_at=None,
        resumes_at=None,
        customer_id=customer_id,
        product_id=product_id,
        discount_id=None,
        checkout_id=None,
        seats=None,
        customer_cancellation_reason=None,
        customer_cancellation_comment=None,
        metadata={},
        custom_field_data=None,
        customer=make_customer(customer_id=customer_id, external_id=external_id),
        product=make_product(product_id=product_id),
        discount=None,
        prices=[],
        meters=[],
        pending_update=None,
    )


def make_state_subscription(  # noqa: PLR0913
    *,
    subscription_id: str = "sub-1",
    product_id: str = "test-starter-id",
    status: str = "active",
    cancel_at_period_end: bool = False,
    current_period_end: str | datetime = "2025-02-01T00:00:00Z",
    amount: int = 2900,
    currency: str = "usd",
) -> CustomerStateSubscription:
    """Build a real CustomerStateSubscription (no customer or customer_id fields)."""
    return CustomerStateSubscription(
        id=subscription_id,
        created_at="2025-01-01T00:00:00Z",
        modified_at=None,
        custom_field_data=None,
        metadata={},
        status=cast("Status", status),
        amount=amount,
        currency=currency,
        recurring_interval="month",
        current_period_start="2025-01-01T00:00:00Z",
        current_period_end=_to_iso(current_period_end),
        trial_start=None,
        trial_end=None,
        cancel_at_period_end=cancel_at_period_end,
        canceled_at=None,
        started_at="2025-01-01T00:00:00Z",
        ends_at=None,
        product_id=product_id,
        discount_id=None,
        meters=[],
    )


def make_customer_state(
    *,
    customer_id: str = "cust-1",
    active_subscriptions: list[CustomerStateSubscription] | None = None,
) -> CustomerStateIndividual:
    """Build a real CustomerStateIndividual carrying the given active subscriptions."""
    return CustomerStateIndividual(
        id=customer_id,
        created_at="2025-01-01T00:00:00Z",
        modified_at=None,
        metadata={},
        external_id=None,
        email="owner@example.com",
        email_verified=True,
        type="individual",
        name="Acme Inc.",
        billing_name=None,
        billing_address=None,
        tax_id=[],
        locale="en",
        organization_id="org-polar-1",
        default_payment_method_id=None,
        deleted_at=None,
        avatar_url=None,
        active_subscriptions=active_subscriptions or [],
        granted_benefits=[],
        active_meters=[],
    )
