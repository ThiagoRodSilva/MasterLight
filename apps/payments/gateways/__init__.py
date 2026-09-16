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

_REGISTRY = {
    "asaas": AsaasGateway,
}


def get_gateway() -> PaymentGateway:
    provider = getattr(settings, "PAYMENT_PROVIDER", "asaas")
    cls = _REGISTRY.get(provider)
    if cls is None:
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            f"PAYMENT_PROVIDER '{provider}' desconhecido. "
            f"Registrados: {', '.join(sorted(_REGISTRY))}."
        )
    return cls()


__all__ = [
    "AsaasGateway",
    "PaymentGateway",
    "ChargeResult",
    "CheckoutResult",
    "PaymentLinkResult",
    "WebhookAuthError",
    "get_gateway",
]
