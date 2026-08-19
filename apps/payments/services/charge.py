"""Cobrança de pedidos com rollback automático em falha."""

from typing import TYPE_CHECKING

from django.contrib import messages
from django.http import HttpRequest

from apps.payments.gateways import ChargeResult, get_gateway

from .billing import resolve_billing

if TYPE_CHECKING:
    from apps.checkout.models import Address, Order


def _cancel_order_if_pending(order: "Order") -> bool:
    """Cancela a Order apenas se estiver em status pendente (OPEN/AWAITING_PAYMENT).

    Retorna True se cancelou, False se não cancelou (já PAID/REFUNDED/etc).
    """
    from apps.checkout.models import Order as OrderModel

    if order.status in (OrderModel.Status.OPEN, OrderModel.Status.AWAITING_PAYMENT):
        order.status = OrderModel.Status.CANCELED
        order.save(update_fields=["status", "updated_at"])
        return True
    return False


def charge_order(
    order: "Order",
    billing_type: str = "PIX",
    credit_card_token: str = "",
    remote_ip: str = "",
) -> ChargeResult:
    """Cria transação inicial e chama gateway configurado."""
    from apps.payments.models import Transaction

    result = get_gateway().charge(
        order,
        billing_type=billing_type,
        credit_card_token=credit_card_token,
        remote_ip=remote_ip,
    )
    if result.transaction_id:
        tx = Transaction.objects.filter(pk=result.transaction_id).first()
        if tx:
            if not result.ok:
                tx.status = Transaction.Status.FAILED
            else:
                # Mantém o status informado pelo gateway (ex.: PENDING no Pix),
                # preservando a semântica: cobrança criada ≠ pagamento confirmado.
                tx.status = result.status or tx.status
            tx.raw_payload = result.raw_payload
            tx.save(update_fields=["status", "raw_payload", "updated_at"])
    return result


def charge_with_rollback(
    order: "Order",
    request: HttpRequest,
    *,
    address: "Address | None" = None,
    fail_message: str = "Falha ao gerar cobrança.",
) -> ChargeResult | None:
    """Dispara a cobrança de uma Order, cancelando-a em qualquer falha.

    Unifica o fluxo cartão/tokenize + `charge_order` + cancelamento que estava
    duplicado entre checkout e aprovação de orçamento. Em falha (`ValueError`
    ou `ok=False`), cancela a Order apenas se estiver pendente (OPEN/AWAITING_PAYMENT),
    registra `messages.error` e retorna `None`; a view faz apenas o redirect.
    Em sucesso, retorna o `ChargeResult`.

    Args:
        order: Pedido a ser cobrado.
        request: Request HTTP com dados de pagamento.
        address: Endereço opcional para cobrança com cartão.
        fail_message: Mensagem de erro padrão.

    Returns:
        ChargeResult em sucesso, None em falha (order já cancelada).
    """
    try:
        params = resolve_billing(request, order.user, address=address)
        result = charge_order(
            order,
            billing_type=params.billing_type,
            credit_card_token=params.credit_card_token,
            remote_ip=params.remote_ip,
        )
    except ValueError as exc:
        _cancel_order_if_pending(order)
        messages.error(request, str(exc) or fail_message)
        return None

    if not result.ok:
        _cancel_order_if_pending(order)
        messages.error(request, result.message or fail_message)
        return None
    return result
