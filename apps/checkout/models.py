"""Pedidos, itens e enderecos."""

from decimal import Decimal

from django.db import models

from apps.accounts.models import CustomUser
from apps.core.models import BaseModel


class Address(BaseModel):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="addresses",
        verbose_name="usuário",
    )
    street = models.CharField(max_length=160, verbose_name="rua")
    number = models.CharField(max_length=20, blank=True, default="", verbose_name="número")
    city = models.CharField(max_length=80, verbose_name="cidade")
    state = models.CharField(max_length=80, verbose_name="estado")
    zip_code = models.CharField(max_length=20, verbose_name="CEP")
    country = models.CharField(max_length=80, default="Brasil", verbose_name="país")

    def __str__(self) -> str:
        return f"{self.street}, {self.number} - {self.city}/{self.state}"


class Order(BaseModel):
    class Status(models.TextChoices):
        OPEN = "open", "Aberto"
        AWAITING_PAYMENT = "awaiting_payment", "Aguardando pagamento"
        PAID = "paid", "Pago"
        CANCELED = "canceled", "Cancelado"
        REFUNDED = "refunded", "Reembolsado"
        SHIPPED = "shipped", "Enviado"
        COMPLETED = "completed", "Concluído"

    class Kind(models.TextChoices):
        SERVICE = "service", "Serviço"
        SUBSCRIPTION = "subscription", "Assinatura"

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SERVICE)
    address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.TextField(blank=True, default="")

    def recompute_total(self) -> Decimal:
        total = Decimal(0)
        for item in self.items.all():
            total += item.line_total
        self.total = total
        self.save(update_fields=["total", "updated_at"])
        return total

    def get_latest_asaas_transaction(self):
        """Retorna a transação Asaas mais recente (pending ou qualquer status)."""
        return (
            self.transactions.filter(provider="asaas", status="pending")
            .select_related("order", "user")
            .order_by("-created_at")
            .first()
            or self.transactions.filter(provider="asaas")
            .select_related("order", "user")
            .order_by("-created_at")
            .first()
        )


class OrderItem(BaseModel):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    service = models.ForeignKey(
        "services.Service",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=160, default="")
    qty = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    @property
    def line_total(self) -> Decimal:
        return (self.unit_price or Decimal(0)) * (self.qty or 0)

    def __str__(self) -> str:
        return f"{self.name} x{self.qty}"

    def save(self, *args, **kwargs):
        if not self.name and self.service_id:
            self.name = self.service.name
        super().save(*args, **kwargs)
