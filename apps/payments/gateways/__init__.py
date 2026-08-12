"""Gateways de pagamento: interface, implementações e resolução de provider."""

from django.conf import settings

from .asaas import AsaasGateway
from .base import (
    ChargeResult,
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
    cls = _REGISTRY.get(provider, ManualGateway)
    return cls()


__all__ = [
    "AsaasGateway",
    "ManualGateway",
    "PaymentGateway",
    "ChargeResult",
    "PaymentLinkResult",
    "WebhookAuthError",
    "get_gateway",
]
