"""Serviços de pagamento - camada de negócio."""

# Re-exporta gateways e dataclasses/errors para compatibilidade
from apps.payments.gateways import (
    AsaasGateway,
    ChargeResult,
    CheckoutResult,
    ManualGateway,
    PaymentGateway,
    PaymentLinkResult,
    WebhookAuthError,
    get_gateway,
)

# Import functions from orchestration module
from apps.payments.orchestration import (
    checkout_or_charge,
    create_checkout_for_order,
    create_payment_link,
    mark_order_paid,
    reverse_order_refund,
    subscribe_plan,
    webhook_handler,
)

__all__ = [
    "create_checkout_for_order",
    "checkout_or_charge",
    "subscribe_plan",
    "create_payment_link",
    "mark_order_paid",
    "reverse_order_refund",
    "webhook_handler",
    "AsaasGateway",
    "ManualGateway",
    "ChargeResult",
    "CheckoutResult",
    "PaymentGateway",
    "PaymentLinkResult",
    "WebhookAuthError",
    "get_gateway",
]
