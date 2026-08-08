"""Context processors globais."""

from django.conf import settings

from .models import SiteSettings


def branding(request):
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
        "STORE_ENABLED": flags.store_enabled,
        "SERVICES_ENABLED": flags.services_enabled,
        "AFFILIATES_ENABLED": flags.affiliates_enabled,
    }
