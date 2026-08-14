"""Gateways de pagamento: interface, implementações e resolução de provider."""

from django.conf import settings

from .asaas import AsaasGateway
from .base import (
    ChargeResult,
    CheckoutResult,
    PaymentGateway,
    PaymentLinkResult,
    WebhookAuthError,
)
from .manual import ManualGateway

_REGISTRY = {
    "manual": ManualGateway,
    "asaas": AsaasGateway,
}


def get_gateway() -> PaymentGateway:
    provider = getattr(settings, "PAYMENT_PROVIDER", "manual")
    cls = _REGISTRY.get(provider)
    if cls is None:
        if getattr(settings, "DEBUG", False):
            # Em dev, provider desconhecido cai no manual (comportamento antigo).
            cls = ManualGateway
        else:
            # Em produção, provider desconhecido é erro de configuração (I1).
            from django.core.exceptions import ImproperlyConfigured

            raise ImproperlyConfigured(
                f"PAYMENT_PROVIDER '{provider}' desconhecido. "
                f"Registrados: {', '.join(sorted(_REGISTRY))}."
            )
    return cls()


__all__ = [
    "AsaasGateway",
    "ManualGateway",
    "PaymentGateway",
    "ChargeResult",
    "CheckoutResult",
    "PaymentLinkResult",
    "WebhookAuthError",
    "get_gateway",
]
