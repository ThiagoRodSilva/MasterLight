"""Forms accounts: signup customizado com role."""

from django import forms

from .models import CustomUser


class CustomSignupForm(forms.Form):
    """Adiciona campo `role` limitado a cliente/afiliado no signup.

    allauth carrega dinamicamente esta classe via ACCOUNT_SIGNUP_FORM_CLASS e
    a usa como base de BaseSignupForm (que adiciona username/email/senhas).
    Por isso esta classe herda apenas forms.Form e implementa `signup`.
    Prestador exige aprovacao manual do admin, por isso nao e exposto aqui.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"] = CustomUser._meta.get_field("role").formfield(
            choices=[
                (CustomUser.Role.CLIENTE, "Cliente"),
                (CustomUser.Role.AFILIADO, "Afiliado"),
            ],
            initial=CustomUser.Role.CLIENTE,
            required=True,
        )

    def signup(self, request, user):
        role = self.cleaned_data.get("role")
        if role not in (CustomUser.Role.CLIENTE, CustomUser.Role.AFILIADO):
            role = CustomUser.Role.CLIENTE
        user.role = role
        user.save(update_fields=["role"])
