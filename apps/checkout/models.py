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
        PRODUCT = "product", "Produto"
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
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PRODUCT)
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

    def decrement_stock(self) -> None:
        """Baixa o estoque dos produtos de um pedido pago (atômico)."""
        for item in self.items.filter(product__isnull=False).select_related("product"):
            product = item.product
            if product.stock >= item.qty:
                product.stock -= item.qty
                product.save(update_fields=["stock", "updated_at"])


class OrderItem(BaseModel):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "shop.Product",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    service = models.ForeignKey(
        "services.Service",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    variant = models.ForeignKey(
        "shop.ProductVariant",
        on_delete=models.SET_NULL,
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
        if not self.name:
            if self.product_id:
                self.name = self.product.name
            elif self.service_id:
                self.name = self.service.name
        super().save(*args, **kwargs)


class Cart:
    """Carrinho armazenado em `request.session` (camada python pura)."""

    SESSION_KEY = "cart"

    def __init__(self, session):
        self.session = session
        cart = self.session.get(self.SESSION_KEY)
        if not isinstance(cart, dict):
            cart = {}
        self.cart = cart

    def __iter__(self):
        for pk, data in self.cart.items():
            yield {
                "pk": pk,
                **data,
                "subtotal": float(data.get("price", 0)) * int(data.get("qty", 0)),
            }

    def __len__(self) -> int:
        return sum(int(item.get("qty", 0)) for item in self.cart.values())

    def add(self, product_pk: str, price: float, name: str, qty: int = 1) -> None:
        key = str(product_pk)
        item = self.cart.get(key, {"qty": 0, "price": float(price), "name": name})
        item["qty"] = int(item.get("qty", 0)) + int(qty)
        item["price"] = float(price)
        item["name"] = name
        self.cart[key] = item
        self.save()

    def remove(self, product_pk: str) -> None:
        self.cart.pop(str(product_pk), None)
        self.save()

    def total(self) -> float:
        return sum(
            float(item.get("price", 0)) * int(item.get("qty", 0)) for item in self.cart.values()
        )

    def clear(self) -> None:
        self.session[self.SESSION_KEY] = {}
        self.session.modified = True

    def save(self) -> None:
        self.session[self.SESSION_KEY] = self.cart
        self.session.modified = True

    def is_empty(self) -> bool:
        return len(self) == 0
