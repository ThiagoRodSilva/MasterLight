from django.apps import AppConfig


class AffiliateConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.affiliate"
    label = "affiliate"

    def ready(self):
        # Import signals to register them
        # Import services to connect approve_referral to order_paid signal
        from . import (
            services,  # noqa: F401
            signals,  # noqa: F401
        )
