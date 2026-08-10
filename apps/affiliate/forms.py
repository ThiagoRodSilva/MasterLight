"""Forms do programa de afiliados."""

from django import forms

from .models import AffiliateProfile


class PixKeyForm(forms.ModelForm):
    """Cadastro/atualização da chave Pix do afiliado (payout)."""

    class Meta:
        model = AffiliateProfile
        fields = ["pix_key"]
        labels = {"pix_key": "Chave Pix"}
        help_texts = {"pix_key": "CPF/CNPJ, e-mail, telefone com DDD ou chave aleatória."}

    def clean_pix_key(self):
        pix_key = self.cleaned_data.get("pix_key") or ""
        pix_key = pix_key.strip()
        if not pix_key:
            raise forms.ValidationError("Informe uma chave Pix para receber os saques.")
        return pix_key
