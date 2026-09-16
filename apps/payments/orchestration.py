"""Servicos orquestracao pagamentos (camada de negocio).

Orquestra gateways (ver `apps/payments.gateways`) e conceitos financeiros:
cobranca de pedido, link de pagamento e webhook.
"""

from dataclasses import asdict

from django.contrib import messages
from django.urls import reverse

from .gateways import (
    AsaasGateway,
    ChargeResult,
    CheckoutResult,
    PaymentGateway,
    PaymentLinkResult,
    WebhookAuthError,
    get_gateway,
)

__all__ = [
    "AsaasGateway",
    "ChargeResult",
    "CheckoutResult",
    "PaymentGateway",
    "PaymentLinkResult",
    "WebhookAuthError",
    "get_gateway",
    "create_checkout_for_order",
    "checkout_or_charge",
    "create_payment_link",
    "mark_order_paid",
    "reverse_order_refund",
    "webhook_handler",
]


def _cancel_order_if_pending(order) -> bool:
    """Cancela a Order apenas se estiver em status pendente (OPEN/AWAITING_PAYMENT).

    Retorna True se cancelou, False se não cancelou (já PAID/REFUNDED/etc).
    """
    from apps.checkout.models import Order as OrderModel

    if order.status in (OrderModel.Status.OPEN, OrderModel.Status.AWAITING_PAYMENT):
        order.status = OrderModel.Status.CANCELED
        order.save(update_fields=["status", "updated_at"])
        return True
    return False


def create_checkout_for_order(
    order,
    request,
    *,
    billing_types: list[str] | None = None,
    charge_type: str = "DETACHED",
) -> CheckoutResult:
    """Cria uma sessão de Checkout hosted para a Order no gateway configurado.

    Monta as URLs de callback absolutas a partir do request e delega ao
    gateway (`create_checkout`), que grava a `Transaction` vinculada ao
    checkout. Providers sem Checkout levantam `ValueError`.
    """
    base = request.build_absolute_uri
    callback_urls = {
        "successUrl": base(
            reverse(
                "payments-checkout-callback", kwargs={"order_pk": order.pk, "outcome": "success"}
            )
        ),
        "cancelUrl": base(
            reverse(
                "payments-checkout-callback", kwargs={"order_pk": order.pk, "outcome": "cancel"}
            )
        ),
        "expiredUrl": base(
            reverse(
                "payments-checkout-callback", kwargs={"order_pk": order.pk, "outcome": "expired"}
            )
        ),
    }
    return get_gateway().create_checkout(
        order,
        billing_types=billing_types,
        charge_type=charge_type,
        callback_urls=callback_urls,
    )


def checkout_or_charge(
    order,
    request,
    *,
    address=None,
    billing_types: list[str] | None = None,
    charge_type: str = "DETACHED",
    fail_message: str = "Falha ao gerar cobrança.",
) -> dict | None:
    """Dispara Checkout hosted (Asaas).

    Usa Checkout hosted quando `PAYMENT_PROVIDER == "asaas"`; caso contrário
    levanta erro. Em qualquer falha, cancela a Order apenas se estiver pendente
    (OPEN/AWAITING_PAYMENT), registra `messages.error` e retorna `None`.
    Em sucesso, retorna um dict com a URL de redirecionamento: `{"url": <hosted>}`.
    """
    from django.conf import settings

    if getattr(settings, "PAYMENT_PROVIDER", "asaas") != "asaas":
        raise ValueError("Apenas o provedor Asaas (checkout hospedado) é suportado.")

    try:
        result = create_checkout_for_order(
            order,
            request,
            billing_types=billing_types,
            charge_type=charge_type,
        )
    except ValueError as exc:
        _cancel_order_if_pending(order)
        messages.error(request, str(exc) or fail_message)
        return None
    if not result.ok or not result.url:
        _cancel_order_if_pending(order)
        messages.error(request, result.message or fail_message)
        return None
    return {"url": result.url}


def create_payment_link(
    *,
    name: str,
    value=None,
    description: str = "",
    billing_type: str = "UNDEFINED",
    charge_type: str = "DETACHED",
    due_date_limit_days=None,
    max_installment_count=None,
    end_date=None,
    external_reference: str = "",
) -> PaymentLinkResult:
    """Gera um link de pagamento avulso no gateway configurado."""
    return get_gateway().create_payment_link(
        name=name,
        value=value,
        description=description,
        billing_type=billing_type,
        charge_type=charge_type,
        due_date_limit_days=due_date_limit_days,
        max_installment_count=max_installment_count,
        end_date=end_date,
        external_reference=external_reference,
    )


def mark_order_paid(tx) -> None:
    """Marca a Order como PAGO quando a transacao vira PAGA.

    Responsabilidade unica do dominio de pagamentos (C1): o signal de
    `post_save` em `apps/payments/signals.py` chama esta funcao, e a comissao
    de afiliado e tratada em `approve_referral` (somente comissao). Idempotente:
    so age na transicao para PAGO. Bloqueia transicoes indevidas: se o pedido
    ja estiver PAID ou REFUNDED, nao ressuscita reembolsado.
    """
    from django.db import transaction as db_transaction

    from apps.checkout.models import Order

    order = tx.order
    if order is None:
        return
    with db_transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        if locked_order.status in (Order.Status.PAID, Order.Status.REFUNDED):
            return
        locked_order.status = Order.Status.PAID
        locked_order.save(update_fields=["status", "updated_at"])


def reverse_order_refund(tx) -> None:
    """Reverte um pedido pago quando a transacao vira REEMBOLSADA (C2).

    Seta a Order para REFUNDED e estorna a comissao ja creditada do afiliado
    (sem deixar saldo negativo), devolvendo o referral para PENDING para
    permitir re-credito num eventual repagamento. Idempotente: so age quando
    a Order ainda esta PAGO.
    """
    from decimal import Decimal

    from django.db import transaction as db_transaction

    from apps.affiliate.models import AffiliateProfile, Referral
    from apps.checkout.models import Order

    order = tx.order
    if order is None:
        return
    with db_transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        if locked_order.status != Order.Status.PAID:
            return
        locked_order.status = Order.Status.REFUNDED
        locked_order.save(update_fields=["status", "updated_at"])

        referral = (
            locked_order.referrals.select_for_update()
            .filter(status=Referral.Status.APPROVED)
            .first()
        )
        if referral is None:
            return
        affiliate = AffiliateProfile.objects.select_for_update().get(pk=referral.affiliate_id)
        commission = referral.commission_amount or Decimal(0)
        affiliate.balance = max(Decimal(0), (affiliate.balance or Decimal(0)) - commission)
        affiliate.save(update_fields=["balance", "updated_at"])
        referral.status = Referral.Status.PENDING
        referral.save(update_fields=["status", "updated_at"])


def webhook_handler(payload, headers) -> dict:
    """Processa webhook generico e retorna dicionario serializavel."""
    result = get_gateway().webhook(payload, headers)
    return asdict(result)
