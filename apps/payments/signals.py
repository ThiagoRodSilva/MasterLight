"""Signals payments: ordem paga/reembolsada + comissao de afiliado.

Responsabilidades:
- `mark_order_paid_on_paid`: marca a Order como PAGO e baixa o estoque (C1).
- `transaction_post_save`: aprova referral/comissao quando a transacao vira
  PAGA (somente comissao; a regra de ordem paga ficou no service de payments).
- `reverse_order_on_refunded`: reverte pedido pago, estoque e comissao (C2).
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.affiliate.services import approve_referral

from .services import mark_order_paid, reverse_order_refund


@receiver(post_save, sender="payments.Transaction")
def mark_order_paid_on_paid(sender, instance, created, **kwargs):
    """Marca a Order como PAGO (com baixa de estoque) quando a tx vira PAGA."""
    if created:
        return
    if instance.status != "paid":
        return
    mark_order_paid(instance)


@receiver(post_save, sender="payments.Transaction")
def transaction_post_save(sender, instance, created, **kwargs):
    """Aprova referral/comissao quando transacao passa a PAGA."""
    if created:
        return
    if instance.status != "paid":
        return
    approve_referral(instance)


@receiver(post_save, sender="payments.Transaction")
def reverse_order_on_refunded(sender, instance, created, **kwargs):
    """Reverte pedido pago (estoque + comissao) quando a tx vira REEMBOLSADA."""
    if created:
        return
    if instance.status != "refunded":
        return
    reverse_order_refund(instance)
