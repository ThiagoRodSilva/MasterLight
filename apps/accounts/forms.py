"""Forms accounts: signup customizado com role e edição de dados."""

from django import forms

from apps.core.models import SiteSettings
from apps.core.validators import validate_brazilian_cpf

from .models import CustomUser, ProviderApplication

_ADDRESS_FIELDS = ["street", "number", "city", "state", "zip_code", "country"]


def _only_digits(value):
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _address_common_fields():
    """Campos de endereço compartilhados entre signup e edição de perfil."""
    return [
        ("street", forms.CharField(max_length=160, label="Rua")),
        ("number", forms.CharField(max_length=20, label="Número")),
        ("city", forms.CharField(max_length=80, label="Cidade")),
        ("state", forms.CharField(max_length=80, label="Estado")),
        ("zip_code", forms.CharField(max_length=20, label="CEP")),
        ("country", forms.CharField(max_length=80, initial="Brasil", label="País")),
    ]


class CustomSignupForm(forms.Form):
    """Form de signup do allauth com role, CPF/telefone e endereço.

    allauth carrega dinamicamente esta classe via ACCOUNT_SIGNUP_FORM_CLASS e
    a usa como base de BaseSignupForm (que adiciona username/email/senhas).
    Por isso esta classe herda apenas forms.Form e implementa `signup`.

    CPF, telefone e endereço são obrigatórios para todos os perfis: o gateway
    de pagamento (Asaas) exige esses dados ao criar o customer, então eles
    nascem completos no cadastro. O candidato a prestador mantém
    `role=cliente` até a aprovação do admin (ProviderApplication pendente).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [
            (CustomUser.Role.CLIENTE, "Cliente"),
            (CustomUser.Role.AFILIADO, "Afiliado"),
        ]
        if SiteSettings.load().provider_registration_enabled:
            choices.append((CustomUser.Role.PRESTADOR, "Prestador"))
        self.fields["role"] = CustomUser._meta.get_field("role").formfield(
            choices=choices,
            initial=CustomUser.Role.CLIENTE,
            required=True,
        )
        self.fields["cpf"] = forms.CharField(
            max_length=14,
            label="CPF",
            validators=[validate_brazilian_cpf],
            help_text="Usado para emitir cobranças e boletos.",
        )
        self.fields["telefone"] = forms.CharField(
            max_length=20,
            label="Telefone",
            help_text="Usado pelo gateway de pagamento.",
        )
        self.fields["bio"] = forms.CharField(
            widget=forms.Textarea,
            required=False,
            label="Bio / especialidades",
            help_text="Aparece no seu perfil público após a aprovação.",
        )
        for name, field in _address_common_fields():
            self.fields[name] = field

    def clean_role(self):
        role = self.cleaned_data.get("role")
        if (role == CustomUser.Role.PRESTADOR) and not SiteSettings.load().provider_registration_enabled:
            raise forms.ValidationError("O cadastro de prestadores está desabilitado.")
        return role

    def clean_cpf(self):
        return _only_digits(self.cleaned_data.get("cpf"))

    def clean_telefone(self):
        return _only_digits(self.cleaned_data.get("telefone"))

    def clean_zip_code(self):
        return _only_digits(self.cleaned_data.get("zip_code"))

    def signup(self, request, user):
        from apps.checkout.models import Address

        role = self.cleaned_data.get("role")
        user.cpf = self.cleaned_data["cpf"]
        user.telefone = self.cleaned_data["telefone"]
        if role == CustomUser.Role.PRESTADOR:
            # Candidato: mantém role=cliente até a aprovação manual do admin.
            user.role = CustomUser.Role.CLIENTE
            user.save(update_fields=["role", "cpf", "telefone"])
            ProviderApplication.objects.create(user=user, bio=self.cleaned_data.get("bio") or "")
        else:
            user.role = role if role == CustomUser.Role.AFILIADO else CustomUser.Role.CLIENTE
            user.save(update_fields=["role", "cpf", "telefone"])
        Address.objects.create(
            user=user,
            street=self.cleaned_data["street"],
            number=self.cleaned_data["number"],
            city=self.cleaned_data["city"],
            state=self.cleaned_data["state"],
            zip_code=self.cleaned_data["zip_code"],
            country=self.cleaned_data["country"],
        )


class SocialSignupCompleteForm(forms.Form):
    """Completamento obrigatório após login social (Google)."""

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        choices = [
            (CustomUser.Role.CLIENTE, "Cliente"),
            (CustomUser.Role.AFILIADO, "Afiliado"),
        ]
        if SiteSettings.load().provider_registration_enabled:
            choices.append((CustomUser.Role.PRESTADOR, "Prestador"))
        self.fields["role"] = CustomUser._meta.get_field("role").formfield(
            choices=choices,
            initial=CustomUser.Role.CLIENTE,
            required=True,
        )
        self.fields["cpf"] = forms.CharField(
            max_length=14,
            label="CPF",
            validators=[validate_brazilian_cpf],
            help_text="Obrigatório para pagamentos (Asaas).",
        )
        self.fields["telefone"] = forms.CharField(
            max_length=20,
            label="Telefone",
            help_text="Obrigatório para pagamentos.",
        )
        for name, field in _address_common_fields():
            self.fields[name] = field

    def clean_role(self):
        role = self.cleaned_data.get("role")
        if (role == CustomUser.Role.PRESTADOR) and not SiteSettings.load().provider_registration_enabled:
            raise forms.ValidationError("O cadastro de prestadores está desabilitado.")
        return role

    def clean_cpf(self):
        return _only_digits(self.cleaned_data.get("cpf"))

    def clean_telefone(self):
        return _only_digits(self.cleaned_data.get("telefone"))

    def clean_zip_code(self):
        return _only_digits(self.cleaned_data.get("zip_code"))

    def save(self, user, sociallogin):
        """Atualiza usuário + cria Address + conecta SocialAccount."""
        from apps.checkout.models import Address

        user.cpf = self.cleaned_data["cpf"]
        user.telefone = self.cleaned_data["telefone"]
        role = self.cleaned_data.get("role")
        if role == CustomUser.Role.PRESTADOR and not SiteSettings.load().provider_registration_enabled:
            role = CustomUser.Role.CLIENTE
        user.role = role
        user.save(update_fields=["cpf", "telefone", "role"])

        Address.objects.create(
            user=user,
            street=self.cleaned_data["street"],
            number=self.cleaned_data["number"],
            city=self.cleaned_data["city"],
            state=self.cleaned_data["state"],
            zip_code=self.cleaned_data["zip_code"],
            country=self.cleaned_data["country"],
        )

        # Conecta SocialAccount definitivamente
        sociallogin.connect(self.request, user)
        return user


class ProfileEditForm(forms.Form):
    """Edição de dados pessoais e de pagamento do usuário.

    Atualiza nome, CPF, telefone e o primeiro endereço ativo (upsert). CPF é
    validado pelos dígitos verificadores — o Asaas exige CPF, telefone e
    endereço completos para criar o customer e cobrar.
    """

    first_name = forms.CharField(max_length=150, required=False, label="Nome")
    last_name = forms.CharField(max_length=150, required=False, label="Sobrenome")
    email = forms.EmailField(disabled=True, label="Email")
    cpf = forms.CharField(max_length=14, label="CPF", validators=[validate_brazilian_cpf])
    telefone = forms.CharField(max_length=20, label="Telefone")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        for name, field in _address_common_fields():
            self.fields[name] = field
        address = self.user.addresses.filter(is_active=True).first()
        self.fields["first_name"].initial = self.user.first_name
        self.fields["last_name"].initial = self.user.last_name
        self.fields["email"].initial = self.user.email
        self.fields["cpf"].initial = self.user.cpf
        self.fields["telefone"].initial = self.user.telefone
        if address is not None:
            for field in _ADDRESS_FIELDS:
                self.fields[field].initial = getattr(address, field)

    def clean_cpf(self):
        return _only_digits(self.cleaned_data.get("cpf"))

    def clean_telefone(self):
        return _only_digits(self.cleaned_data.get("telefone"))

    def clean_zip_code(self):
        return _only_digits(self.cleaned_data.get("zip_code"))

    def save(self):
        from apps.checkout.models import Address

        self.user.first_name = self.cleaned_data.get("first_name") or ""
        self.user.last_name = self.cleaned_data.get("last_name") or ""
        self.user.cpf = self.cleaned_data["cpf"]
        self.user.telefone = self.cleaned_data["telefone"]
        self.user.save(update_fields=["first_name", "last_name", "cpf", "telefone"])
        data = {field: self.cleaned_data[field] for field in _ADDRESS_FIELDS}
        address = self.user.addresses.filter(is_active=True).first()
        if address is None:
            Address.objects.create(user=self.user, **data)
        else:
            for field, value in data.items():
                setattr(address, field, value)
            address.save(update_fields=_ADDRESS_FIELDS)
