"""Forms do app shop (preparação para gestão de catálogo)."""

from django import forms

from .models import Category, Product, ProductImage, ProductVariant


class CategoryForm(forms.ModelForm):
    """Form para categoria de produto."""

    class Meta:
        model = Category
        fields = ["name", "is_active"]


class ProductForm(forms.ModelForm):
    """Form para produto da loja."""

    class Meta:
        model = Product
        fields = ["sku", "name", "description", "price", "stock", "category", "featured", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sku"].help_text = "Código único do produto (ex.: ML-001)"


class ProductVariantForm(forms.ModelForm):
    """Form para variante de produto (tamanho, cor, etc.)."""

    class Meta:
        model = ProductVariant
        fields = ["name", "value", "price_adjustment", "stock"]


class ProductImageForm(forms.ModelForm):
    """Form para imagem de produto."""

    class Meta:
        model = ProductImage
        fields = ["image", "alt", "order"]
