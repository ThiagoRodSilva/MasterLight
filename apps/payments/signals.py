"""Signals payments: dispara aprovacao referral quando transacao paga."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.affiliate.services import approve_referral


@receiver(post_save, sender="payments.Transaction")
def transaction_post_save(sender, instance, created, **kwargs):
    """Aprova referral/comissao quando transacao passa a PAGA."""
    if created:
        return
    if instance.status != "paid":
        return
    approve_referral(instance)
