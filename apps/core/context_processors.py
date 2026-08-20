"""Context processors globais."""

from typing import Any

from django.conf import settings
from django.http import HttpRequest

from .models import SiteSettings


def cart_count(request: HttpRequest) -> dict[str, Any]:
    """Conta total de itens no carrinho da sessão (badge do navbar)."""
    from apps.checkout.models import Cart

    return {"CART_COUNT": len(Cart(request.session))}


def branding(request: HttpRequest) -> dict[str, Any]:
    flags = SiteSettings.load()
    return {
        "BRAND_NAME": getattr(request, "brand_name", "MasterLight"),
        "BRAND_TAGLINE": "Serviços elétricos para sua casa e negócio",
        "BRAND_PALETTE": {
            "primary": "#FFC107",
            "primary_alt": "#E6A800",
            "secondary": "#111111",
            "secondary_alt": "#2d2d2d",
            "accent": "#198754",
            "dark": "#111111",
            "light": "#ffffff",
            "bg_light": "#f8f8f6",
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
