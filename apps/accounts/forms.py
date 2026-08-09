"""Forms accounts: signup customizado com role."""

from django import forms

from apps.core.models import SiteSettings

from .models import CustomUser, ProviderApplication


class CustomSignupForm(forms.Form):
    """Form de signup do allauth com role e dados de prestador.

    allauth carrega dinamicamente esta classe via ACCOUNT_SIGNUP_FORM_CLASS e
    a usa como base de BaseSignupForm (que adiciona username/email/senhas).
    Por isso esta classe herda apenas forms.Form e implementa `signup`.

    O candidato a prestador mantém `role=cliente` até a aprovação do admin
    (ProviderApplication pendente); o campo `role` nunca é `prestador`.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [
            (CustomUser.Role.CLIENTE, "Cliente"),
            (CustomUser.Role.AFILIADO, "Afiliado"),
        ]
        if SiteSettings.load().provider_registration_enabled:
            choices.append((CustomUser.Role.PRESTADOR, "Prestador (aprovado pelo admin)"))
        self.fields["role"] = CustomUser._meta.get_field("role").formfield(
            choices=choices,
            initial=CustomUser.Role.CLIENTE,
            required=True,
        )
        self.fields["cpf"] = forms.CharField(
            max_length=14,
            required=False,
            label="CPF",
            help_text="Obrigatório para prestadores.",
        )
        self.fields["telefone"] = forms.CharField(
            max_length=20,
            required=False,
            label="Telefone",
            help_text="Obrigatório para prestadores.",
        )
        self.fields["bio"] = forms.CharField(
            widget=forms.Textarea,
            required=False,
            label="Bio / especialidades",
            help_text="Aparece no seu perfil público após a aprovação.",
        )

    def clean_role(self):
        role = self.cleaned_data.get("role")
        if (role == CustomUser.Role.PRESTADOR) and not SiteSettings.load().provider_registration_enabled:
            raise forms.ValidationError("O cadastro de prestadores está desabilitado.")
        return role

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role")
        if role == CustomUser.Role.PRESTADOR:
            if not cleaned.get("cpf"):
                self.add_error("cpf", "CPF é obrigatório para prestadores.")
            if not cleaned.get("telefone"):
                self.add_error("telefone", "Telefone é obrigatório para prestadores.")
        if cleaned.get("cpf"):
            cleaned["cpf"] = "".join(ch for ch in cleaned["cpf"] if ch.isdigit())
        return cleaned

    def signup(self, request, user):
        role = self.cleaned_data.get("role")
        user.cpf = self.cleaned_data.get("cpf") or ""
        user.telefone = self.cleaned_data.get("telefone") or ""
        if role == CustomUser.Role.PRESTADOR:
            # Candidato: mantém role=cliente até a aprovação manual do admin.
            user.role = CustomUser.Role.CLIENTE
            user.save(update_fields=["role", "cpf", "telefone"])
            ProviderApplication.objects.create(user=user, bio=self.cleaned_data.get("bio") or "")
            return
        user.role = role if role == CustomUser.Role.AFILIADO else CustomUser.Role.CLIENTE
        user.save(update_fields=["role", "cpf", "telefone"])
