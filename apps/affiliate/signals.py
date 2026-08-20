"""Signals do programa de afiliados."""

from django.dispatch import Signal, receiver

from .services import approve_referral

# Signal emitido quando um pedido é pago (transaction.status == "paid")
# Args: order, transaction
order_paid = Signal()


@receiver(order_paid)
def handle_order_paid(sender, order, transaction, **kwargs):
    """Handler para order_paid: aprova referral se houver."""
    if transaction.status == "paid":
        approve_referral(transaction)
