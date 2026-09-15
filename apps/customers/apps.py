from django.apps import AppConfig


class CustomersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.customers"
    label = "customers"

    def ready(self) -> None:
        from apps.customers import signals  # noqa: F401, PLC0415
