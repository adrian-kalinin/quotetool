from apps.customers.models import Address
from apps.customers.models import Customer
from apps.organizations.models import Organization


def create_address(organization: Organization, **fields) -> Address:
    """Create an Address with sensible defaults."""
    defaults = {
        "line1": "1 Main St",
        "city": "Berlin",
        "postal_code": "10115",
        "country": "Germany",
    }
    defaults.update(fields)
    return Address.objects.create(organization=organization, **defaults)


def create_customer(organization: Organization, **fields) -> Customer:
    """Create a Customer with an owned billing Address unless one is provided."""
    address = fields.pop("billing_address", None) or create_address(organization)
    defaults = {
        "type": Customer.Type.CORPORATE,
        "company_name": "Acme GmbH",
        "email": "billing@acme.test",
    }
    defaults.update(fields)
    return Customer.objects.create(organization=organization, billing_address=address, **defaults)


def customer_form_data(**overrides) -> dict[str, object]:
    """Return a valid customer form payload with the given overrides."""
    data = {
        "type": Customer.Type.CORPORATE,
        "company_name": "Acme GmbH",
        "email": "billing@acme.test",
        "address_line1": "1 Main St",
        "address_city": "Berlin",
        "address_postal_code": "10115",
        "address_country": "Germany",
    }
    data.update(overrides)
    return data
