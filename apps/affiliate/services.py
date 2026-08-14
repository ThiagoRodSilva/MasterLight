"""Servicos programa afiliados (camada de aplicacao)."""

from decimal import Decimal

from django.db import transaction as db_transaction
from django.db.models import F


def approve_referral(tx) -> int | None:
    """Aprova referral pendente e credita a comissao no saldo do afiliado.

    Apenas a parte de comissao: a marcacao do pedido como PAGO e a baixa de
    estoque sao responsabilidade de `apps.payments.services.mark_order_paid`
    (signal em `apps/payments/signals.py`), que mantem a regra no dominio de
    pagamentos. Retorna o pk do referral atualizado ou None sem referral.
    """
    if tx.status != "paid":
        return None

    order = tx.order
    referral_qs = order.referrals.filter(status="pending") if order is not None else None
    referral = referral_qs.first() if referral_qs else None

    if referral is None:
        return None

    with db_transaction.atomic():
        referral.status = referral.Status.APPROVED
        referral.save(update_fields=["status", "updated_at"])

        affiliate = referral.affiliate
        commission = referral.commission_amount or Decimal(0)
        affiliate.balance = F("balance") + commission
        affiliate.save(update_fields=["balance", "updated_at"])

        return referral.pk


def create_payout_request(profile):
    """Cria solicitacao de saque atomica para o afiliado.

    Valida saldo > 0, cria PayoutRequest e zera o saldo. Retorna a solicitacao.
    Levanta ValueError se saldo for menor/igual a zero.
    """
    from .models import AffiliateProfile, PayoutRequest

    amount = None
    payout = None
    with db_transaction.atomic():
        if not (profile.pix_key or "").strip():
            raise ValueError("Cadastre uma chave Pix para realizar o saque.")
        locked = AffiliateProfile.objects.select_for_update().filter(pk=profile.pk).first()
        if locked is None or locked.balance is None or locked.balance <= Decimal(0):
            raise ValueError("Saldo insuficiente para saque.")

        amount = locked.balance
        payout = PayoutRequest.objects.create(affiliate=locked, amount=amount)
        locked.balance = Decimal(0)
        locked.save(update_fields=["balance", "updated_at"])

    return payout
