"""Servicos programa afiliados (camada de aplicacao)."""

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction as db_transaction
from django.db.models import F

if TYPE_CHECKING:
    from .models import Referral


def _resolve_commission_rate(order_item) -> Decimal:
    """Resolve a taxa de comissão para um item do pedido.

    Prioridade:
    1. Service.affiliate_commission_rate
    2. AffiliateProfile.commission_rate (fallback global)
    """
    # Service (OrderItem.service)
    if order_item.service_id:
        rate = getattr(order_item.service, "affiliate_commission_rate", None)
        if rate is not None:
            return rate

    # Fallback: taxa global do afiliado (será passada pelo caller)
    return Decimal("0")


def calculate_commission(order_item, affiliate_rate: Decimal) -> Decimal:
    """Calcula comissão para um OrderItem.

    Args:
        order_item: OrderItem com product/service e unit_price/qty
        affiliate_rate: Taxa default do afiliado (AffiliateProfile.commission_rate)

    Returns:
        Decimal quantizado para 2 casas (centavos)
    """
    rate = _resolve_commission_rate(order_item) or affiliate_rate
    subtotal = order_item.unit_price * order_item.qty
    commission = (subtotal * rate).quantize(Decimal("0.01"))
    return commission


def create_referral(
    ref_code: str,
    user,
    order,
    affiliate_rate: Decimal | None = None,
) -> "Referral | None":
    """Cria Referral para o pedido, se código de afiliado válido.

    Comissão calculada por item (prioridade: product/service/template > afiliado).
    Bloqueia auto-referral (affil.user_id == user.pk).
    Idempotente: se já existe referral para este (affiliate, order), retorna o existente.

    Args:
        ref_code: Código do afiliado (do cookie ?ref=)
        user: Usuário que fez o pedido (referred)
        order: Order recém-criado
        affiliate_rate: Taxa default do afiliado (opcional, busca do perfil se não passado)

    Returns:
        Referral criado/buscado ou None
    """
    from django.db import IntegrityError

    from apps.affiliate.models import AffiliateProfile, Referral

    affil = (
        AffiliateProfile.objects.select_related("user")
        .filter(code=ref_code, is_active=True)
        .first()
    )
    if not affil or affil.user_id == user.pk:
        return None

    rate = affiliate_rate or affil.commission_rate

    # Calcula comissão total somando por item
    total_commission = Decimal("0")
    for item in order.items.all():
        total_commission += calculate_commission(item, rate)

    try:
        return Referral.objects.create(
            affiliate=affil,
            referred=user,
            order=order,
            commission_rate=rate,
            commission_amount=total_commission,
        )
    except IntegrityError:
        return Referral.objects.filter(affiliate=affil, order=order, is_active=True).first()


def approve_referral(tx) -> int | None:
    """Aprova referral pendente e credita a comissão no saldo do afiliado.

    Apenas a parte de comissão: a marcação do pedido como PAGO e a baixa de
    estoque são responsabilidade de apps.payments.services.mark_order_paid
    (signal em apps/payments/signals.py), que mantém a regra no domínio de
    pagamentos. Retorna o pk do referral atualizado ou None sem referral.
    Idempotente: trava o referral e o perfil do afiliado para evitar crédito
    duplicado em webhooks concorrentes. Se o referral já estiver APPROVED,
    retorna o pk sem creditar comissão novamente.
    """
    if tx.status != "paid":
        return None

    order = tx.order
    if order is None:
        return None

    from django.db import transaction as db_transaction

    with db_transaction.atomic():
        # Busca referral pendente OU já aprovado (idempotente)
        referral = (
            order.referrals.select_for_update()
            .filter(status__in=["pending", "approved"], is_active=True)
            .first()
        )
        if referral is None:
            return None

        # Se já aprovado, retorna pk sem creditar novamente
        if referral.status == referral.Status.APPROVED:
            return referral.pk

        referral.status = referral.Status.APPROVED
        referral.save(update_fields=["status", "updated_at"])

        from apps.affiliate.models import AffiliateProfile

        affiliate = AffiliateProfile.objects.select_for_update().get(pk=referral.affiliate_id)
        commission = referral.commission_amount or Decimal("0")
        affiliate.balance = F("balance") + commission
        affiliate.save(update_fields=["balance", "updated_at"])

        return referral.pk


def create_payout_request(profile):
    """Cria solicitação de saque atômica para o afiliado.

    Valida saldo > 0, cria PayoutRequest e zera o saldo. Retorna a solicitação.
    Levanta ValueError se saldo for menor/igual a zero.
    """
    from .models import AffiliateProfile, PayoutRequest

    amount = None
    payout = None
    with db_transaction.atomic():
        if not (profile.pix_key or "").strip():
            raise ValueError("Cadastre uma chave Pix para realizar o saque.")
        locked = AffiliateProfile.objects.select_for_update().filter(pk=profile.pk).first()
        if locked is None or locked.balance is None or locked.balance <= Decimal("0"):
            raise ValueError("Saldo insuficiente para saque.")

        amount = locked.balance
        payout = PayoutRequest.objects.create(affiliate=locked, amount=amount)
        locked.balance = Decimal("0")
        locked.save(update_fields=["balance", "updated_at"])

    return payout
