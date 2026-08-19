"""Serviços de pagamento - camada de negócio.

Módulos:
- billing: Resolução de forma de pagamento e tokenização de cartão
- charge: Cobrança de pedidos com rollback automático
- subscription: Assinaturas recorrentes
- payment_link: Links de pagamento avulsos
- checkout: Checkout hospedado (Asaas)
- order_transition: Transições de status de pedido (pago/reembolsado)
- webhook: Processamento genérico de webhook
"""

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

from .billing import BillingParams, prepare_card_payload, resolve_billing
from .charge import charge_order, charge_with_rollback
from .checkout import checkout_or_charge, create_checkout_for_order
from .order_transition import mark_order_paid, reverse_order_refund
from .payment_link import create_payment_link
from .subscription import subscribe_plan
from .webhook import webhook_handler

__all__ = [
    "BillingParams",
    "prepare_card_payload",
    "resolve_billing",
    "charge_order",
    "charge_with_rollback",
    "subscribe_plan",
    "create_payment_link",
    "create_checkout_for_order",
    "checkout_or_charge",
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
