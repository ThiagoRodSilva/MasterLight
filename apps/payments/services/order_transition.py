"""Transições de status de pedido (pago/reembolsado)."""

import logging
from decimal import Decimal

from django.db import transaction as db_transaction

from apps.payments.exceptions import (
    InsufficientStockError,
    TransactionNotFoundError,
)

logger = logging.getLogger(__name__)


def mark_order_paid(tx) -> None:
    """Marca a Order como PAGO e baixa o estoque quando a transação vira PAGA.

    Responsabilidade única do domínio de pagamentos (C1): o signal de
    `post_save` em `apps/payments/signals.py` chama esta função, e a comissão
    de afiliado é tratada em `approve_referral` (somente comissão). Idempotente:
    só age na transição para PAGO. Bloqueia transições indevidas: se o pedido
    já estiver PAID ou REFUNDED, não re-baixa estoque nem ressuscita reembolsado.
    """
    from apps.checkout.models import Order

    order = tx.order
    if order is None:
        logger.warning(
            "mark_order_paid: transação sem order associado",
            extra={"transaction_id": str(tx.pk), "tx_status": tx.status},
        )
        return

    try:
        with db_transaction.atomic():
            locked_order = Order.objects.select_for_update().get(pk=order.pk)
            if locked_order.status in (Order.Status.PAID, Order.Status.REFUNDED):
                logger.info(
                    "mark_order_pedido: pedido já em status terminal, ignorando",
                    extra={
                        "order_id": str(locked_order.pk),
                        "current_status": locked_order.status,
                        "transaction_id": str(tx.pk),
                    },
                )
                return
            locked_order.status = Order.Status.PAID
            locked_order.save(update_fields=["status", "updated_at"])
            locked_order.decrement_stock()

        logger.info(
            "mark_order_pedido: pedido marcado como pago e estoque baixado",
            extra={
                "order_id": str(locked_order.pk),
                "transaction_id": str(tx.pk),
                "order_total": str(locked_order.total),
            },
        )

    except Exception as exc:
        logger.exception(
            "mark_order_pedido: erro ao processar pagamento",
            extra={"order_id": str(order.pk), "transaction_id": str(tx.pk)},
        )
        raise InsufficientStockError(
            "Falha ao baixar estoque do pedido", provider=tx.provider, external_id=tx.external_id
        ) from exc


def reverse_order_refund(tx) -> None:
    """Reverte um pedido pago quando a transação vira REEMBOLSADA (C2).

    Seta a Order para REFUNDED, repõe o estoque e estorna a comissão já
    creditada do afiliado (sem deixar saldo negativo), devolvendo o referral
    para PENDING para permitir re-crédito num eventual repagamento. Idempotente:
    só age quando a Order ainda está PAGO.
    """
    from apps.affiliate.models import AffiliateProfile, Referral
    from apps.checkout.models import Order

    order = tx.order
    if order is None:
        logger.warning(
            "reverse_order_refund: transação sem order associado",
            extra={"transaction_id": str(tx.pk), "tx_status": tx.status},
        )
        return

    try:
        with db_transaction.atomic():
            locked_order = Order.objects.select_for_update().get(pk=order.pk)
            if locked_order.status != Order.Status.PAID:
                logger.info(
                    "reverse_order_refund: pedido não está pago, ignorando",
                    extra={
                        "order_id": str(locked_order.pk),
                        "current_status": locked_order.status,
                        "transaction_id": str(tx.pk),
                    },
                )
                return
            locked_order.status = Order.Status.REFUNDED
            locked_order.save(update_fields=["status", "updated_at"])
            locked_order.restore_stock()

            referral = locked_order.referrals.select_for_update().filter(
                status=Referral.Status.APPROVED
            ).first()
            if referral is None:
                logger.info(
                    "reverse_order_refund: nenhum referral aprovado para estornar",
                    extra={"order_id": str(locked_order.pk), "transaction_id": str(tx.pk)},
                )
                return

            affiliate = AffiliateProfile.objects.select_for_update().get(pk=referral.affiliate_id)
            commission = referral.commission_amount or Decimal(0)
            affiliate.balance = max(Decimal(0), (affiliate.balance or Decimal(0)) - commission)
            affiliate.save(update_fields=["balance", "updated_at"])
            referral.status = Referral.Status.PENDING
            referral.save(update_fields=["status", "updated_at"])

        logger.info(
            "reverse_order_refund: pedido reembolsado, estoque reposto e comissão estornada",
            extra={
                "order_id": str(locked_order.pk),
                "transaction_id": str(tx.pk),
                "referral_id": str(referral.pk),
                "affiliate_id": str(affiliate.pk),
                "commission_amount": str(commission),
            },
        )

    except Exception as exc:
        logger.exception(
            "reverse_order_refund: erro ao processar reembolso",
            extra={"order_id": str(order.pk), "transaction_id": str(tx.pk)},
        )
        raise TransactionNotFoundError(
            "Falha ao processar reembolso do pedido", provider=tx.provider, external_id=tx.external_id
        ) from exc
