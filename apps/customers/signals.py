from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.customers.models import Address
from apps.customers.models import Customer


@receiver(post_delete, sender=Customer)
def delete_owned_billing_address(instance: Customer, **_kwargs) -> None:
    """Delete a customer's owned billing address when the customer is deleted."""
    if instance.billing_address_id is not None:
        Address.objects.filter(pk=instance.billing_address_id).delete()
