"""Forms do programa de afiliados."""

import re

from django import forms

from .models import AffiliateProfile

# Regex patterns para validação de chaves Pix
CPF_PATTERN = re.compile(r"^\d{11}$")
CNPJ_PATTERN = re.compile(r"^\d{14}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^\+?55\d{10,11}$")  # 55 + DDD + número
RANDOM_KEY_PATTERN = re.compile(r"^[a-f0-9]{32}$")  # Chave aleatória (32 chars hex)


class PixKeyForm(forms.ModelForm):
    """Cadastro/atualização da chave Pix do afiliado (payout)."""

    class Meta:
        model = AffiliateProfile
        fields = ["pix_key"]
        labels = {"pix_key": "Chave Pix"}
        help_texts = {
            "pix_key": "CPF (11 dígitos), CNPJ (14 dígitos), e-mail, telefone com DDD (ex.: 5511999999999) ou chave aleatória (32 caracteres hex)."
        }

    def clean_pix_key(self):
        pix_key = self.cleaned_data.get("pix_key") or ""
        pix_key = pix_key.strip().lower()
        if not pix_key:
            raise forms.ValidationError("Informe uma chave Pix para receber os saques.")

        # Valida formatos aceitos pelo Pix
        is_valid = (
            CPF_PATTERN.match(pix_key)
            or CNPJ_PATTERN.match(pix_key)
            or EMAIL_PATTERN.match(pix_key)
            or PHONE_PATTERN.match(pix_key)
            or RANDOM_KEY_PATTERN.match(pix_key)
        )

        if not is_valid:
            raise forms.ValidationError(
                "Formato de chave Pix inválido. Use: CPF (11 dígitos), CNPJ (14 dígitos), "
                "e-mail, telefone com DDD (ex.: 5511999999999) ou chave aleatória (32 caracteres hex)."
            )

        return pix_key
