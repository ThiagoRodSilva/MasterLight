"""Signals payments: ordem paga/reembolsada + comissao de afiliado.

Responsabilidades:
- `mark_order_paid_on_paid`: marca a Order como PAGO e baixa o estoque (C1).
- `transaction_post_save`: emite signal order_paid quando a transacao vira PAGA.
- `reverse_order_on_refunded`: reverte pedido pago, estoque e comissao (C2).
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.affiliate.signals import order_paid

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
    """Emite signal order_paid quando transacao passa a PAGA (afiliado ouve)."""
    if created:
        return
    if instance.status != "paid":
        return
    # Emite signal para que o app affiliate processe a comissao
    order_paid.send(sender=None, order=instance.order, transaction=instance)


@receiver(post_save, sender="payments.Transaction")
def reverse_order_on_refunded(sender, instance, created, **kwargs):
    """Reverte pedido pago (estoque + comissao) quando a tx vira REEMBOLSADA."""
    if created:
        return
    if instance.status != "refunded":
        return
    reverse_order_refund(instance)
