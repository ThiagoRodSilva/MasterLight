"""Catalogo de produtos da loja."""

from django.db import models

from apps.core.models import BaseModel, RandomSlugMixin
from apps.core.validators import validate_image_url


class Category(BaseModel, RandomSlugMixin):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True, editable=False)

    class Meta:
        verbose_name = "Categoria de Produto"
        verbose_name_plural = "Categorias de Produtos"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Product(BaseModel, RandomSlugMixin):
    sku = models.CharField(max_length=40, unique=True, db_index=True)
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True, editable=False)
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(max_digits=12, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    featured = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"

    @property
    def cover(self):
        return self.images.first()


class ProductVariant(BaseModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
    )
    name = models.CharField(max_length=80)  # ex: Tamanho M
    value = models.CharField(max_length=80)  # ex: M
    price_adjustment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.product.name} - {self.name}: {self.value}"


class ProductImage(BaseModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.URLField(validators=[validate_image_url])
    alt = models.CharField(max_length=160, blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self) -> str:
        return self.alt or self.product.name
