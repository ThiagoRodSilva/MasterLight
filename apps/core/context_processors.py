"""Context processors globais."""

from typing import Any

from django.conf import settings
from django.http import HttpRequest

from .models import SiteSettings


def branding(request: HttpRequest) -> dict[str, Any]:
    flags = SiteSettings.load()
    return {
        "BRAND_NAME": getattr(request, "brand_name", "MasterLight"),
        "BRAND_TAGLINE": "Serviços elétricos para sua casa e negócio",
        "BRAND_PALETTE": {
            "primary": "#FFC107",
            "primary_alt": "#FFD600",
            "dark": "#111111",
            "light": "#FFFFFF",
        },
        "AFFILIATE_COOKIE_NAME": settings.AFFILIATE_COOKIE_NAME,
        "CARD_ENABLED": settings.PAYMENT_PROVIDER == "asaas",
        "BOLETO_ENABLED": settings.PAYMENT_PROVIDER == "asaas",
        "PAYLINK_ENABLED": settings.PAYMENT_PROVIDER == "asaas",
        "CHECKOUT_HOSTED": settings.PAYMENT_PROVIDER == "asaas",
        "STORE_ENABLED": flags.store_enabled,
        "SERVICES_ENABLED": flags.services_enabled,
        "AFFILIATES_ENABLED": flags.affiliates_enabled,
        "MAINTENANCE_ENABLED": flags.maintenance_enabled,
        "PROVIDER_REGISTRATION_ENABLED": flags.provider_registration_enabled,
    }
