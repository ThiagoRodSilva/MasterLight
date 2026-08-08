"""Transacoes e gateway abstrato de pagamento."""

from django.db import models

from apps.accounts.models import CustomUser
from apps.checkout.models import Order
from apps.core.models import BaseModel


class Transaction(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        AUTHORIZED = "authorized", "Autorizada"
        PAID = "paid", "Paga"
        FAILED = "failed", "Falhou"
        REFUNDED = "refunded", "Reembolsada"

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    provider = models.CharField(max_length=40)
    external_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    raw_payload = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return f"Tx {self.provider}/{self.pk} {self.status}"
