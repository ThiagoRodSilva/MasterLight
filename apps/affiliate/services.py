"""Servicos programa afiliados (camada de aplicacao)."""

from decimal import Decimal

from django.conf import settings
from django.db import transaction as db_transaction
from django.db.models import F


def approve_referral(tx) -> int | None:
    """Aprova referral pendente e credita a comissao no saldo do afiliado.

    Apenas a parte de comissao: a marcacao do pedido como PAGO e a baixa de
    estoque sao responsabilidade de `apps.payments.services.mark_order_paid`
    (signal em `apps/payments/signals.py`), que mantem a regra no dominio de
    pagamentos. Retorna o pk do referral atualizado ou None sem referral.
    Idempotente: trava o referral e o perfil do afiliado para evitar credito
    duplicado em webhooks concorrentes. Se o referral ja estiver APPROVED,
    retorna o pk sem creditar comissao novamente.
    """
    if tx.status != "paid":
        return None

    order = tx.order
    if order is None:
        return None

    from django.db import transaction as db_transaction

    with db_transaction.atomic():
        # Busca referral pendente OU ja aprovado (idempotente)
        referral = order.referrals.select_for_update().filter(
            status__in=["pending", "approved"], is_active=True
        ).first()
        if referral is None:
            return None

        # Se ja aprovado, retorna pk sem creditar novamente
        if referral.status == referral.Status.APPROVED:
            return referral.pk

        referral.status = referral.Status.APPROVED
        referral.save(update_fields=["status", "updated_at"])

        from apps.affiliate.models import AffiliateProfile

        affiliate = AffiliateProfile.objects.select_for_update().get(pk=referral.affiliate_id)
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


def create_referral_from_request(request, order):
    """Cria Referral para o pedido, se cookie ref valido.

    Comissao calculada sobre order.total (produtos + servicos + assinaturas).
    Bloqueia auto-referral (affil.user_id == request.user.pk).
    Idempotente: se ja existe referral para este (affiliate, order), retorna o existente.
    """
    from django.db import IntegrityError

    from apps.affiliate.models import AffiliateProfile, Referral

    ref_code = request.COOKIES.get(settings.AFFILIATE_COOKIE_NAME)
    if not ref_code:
        return None
    affil = AffiliateProfile.objects.select_related("user").filter(code=ref_code, is_active=True).first()
    if not affil or affil.user_id == request.user.pk:
        return None

    # Tenta criar; se ja existe (unique constraint), busca o existente
    try:
        return Referral.objects.create(
            affiliate=affil,
            referred=request.user,
            order=order,
            commission_rate=affil.commission_rate,
            commission_amount=order.total * affil.commission_rate,
        )
    except IntegrityError:
        # Unique constraint violada - referral ja existe para este affiliate+order
        return Referral.objects.filter(affiliate=affil, order=order, is_active=True).first()
