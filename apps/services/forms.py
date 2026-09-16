"""Forms do app services."""

from decimal import Decimal
from typing import Any

from django import forms
from django.core.validators import MinValueValidator

from .models import Service, ServiceRequest


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "category", "description", "base_price", "image", "is_active"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["image"].help_text = "Cole o link direto da imagem — .jpg, .png, .webp, etc."


class ServiceRequestForm(forms.ModelForm):
    class Meta:
        model = ServiceRequest
        fields = ["prestador", "address", "scheduled_at", "notes"]

    def __init__(self, *args: Any, service: Service | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if service is not None:
            active_providers = service.providers.filter(is_active=True)
            self.fields["prestador"].queryset = active_providers
            if active_providers.count() == 1:
                self.initial["prestador"] = active_providers.first()


class QuoteForm(forms.ModelForm):
    """Formulário para o prestador enviar o orçamento (preço final)."""

    class Meta:
        model = ServiceRequest
        fields = ["final_price"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["final_price"].validators = [MinValueValidator(Decimal("0.00"))]
        self.fields[
            "final_price"
        ].help_text = "Preço final do orçamento. Deixe em branco para usar o preço base do serviço."

    def clean_final_price(self) -> Decimal | None:
        final_price = self.cleaned_data.get("final_price")
        if final_price is not None and final_price < Decimal("0.00"):
            raise forms.ValidationError("O preço não pode ser negativo.")
        return final_price
