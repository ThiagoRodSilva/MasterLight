"""Modelos do programa de afiliados."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.accounts.models import CustomUser
from apps.core.models import BaseModel
from apps.core.utils import generate_code


class AffiliateProfile(BaseModel):
    """Perfil afiliado vinculado ao CustomUser (1:1).

    Cada usuario ganha perfil automaticamente (signal accounts.create_affiliate_profile).
    `code` e o tracking code publico usado em ?ref=CODE e cookies.
    """

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="affiliate_profile",
    )
    code = models.CharField(max_length=20, unique=True, db_index=True)
    pix_key = models.CharField(max_length=120, blank=True, default="")
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=settings.AFFILIATE_DEFAULT_COMMISSION_RATE,
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Perfil de Afiliado"
        verbose_name_plural = "Perfis de Afiliados"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_code(10)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Affiliate {self.user.email} ({self.code})"


class Referral(BaseModel):
    """Indicacao de um pedido a um afiliado (gera comissao quando pago)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        APPROVED = "approved", "Aprovada"
        REJECTED = "rejected", "Rejeitada"
        PAID = "paid", "Paga"
        CANCELED = "canceled", "Cancelada"

    affiliate = models.ForeignKey(
        AffiliateProfile,
        on_delete=models.PROTECT,
        related_name="referrals",
    )
    referred = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals_received",
    )
    order = models.ForeignKey(
        "checkout.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=settings.AFFILIATE_DEFAULT_COMMISSION_RATE
    )

    class Meta:
        verbose_name = "Indicação"
        verbose_name_plural = "Indicações"
        constraints = [
            models.UniqueConstraint(
                fields=["affiliate", "order"],
                condition=Q(order__isnull=False),
                name="uniq_referral_affiliate_order",
            )
        ]

    def __str__(self) -> str:
        return f"Referral {self.affiliate.code} -> {self.status}"


class PayoutRequest(BaseModel):
    """Solicitacao de saque do afiliado."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        PAID = "paid", "Paga"
        REJECTED = "rejected", "Rejeitada"

    affiliate = models.ForeignKey(
        AffiliateProfile,
        on_delete=models.PROTECT,
        related_name="payouts",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return f"Payout {self.affiliate.code} {self.amount} ({self.status})"
