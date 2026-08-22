"""Forms do app checkout."""

from django import forms

from .models import Address


class AddressForm(forms.ModelForm):
    """Form para criação/edição de endereço do usuário."""

    class Meta:
        model = Address
        fields = ["street", "number", "city", "state", "zip_code", "country"]
