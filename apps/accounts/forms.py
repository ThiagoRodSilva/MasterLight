"""Forms accounts: signup customizado com role e edição de dados."""

from django import forms

from apps.core.models import SiteSettings
from apps.core.validators import validate_brazilian_cpf

from .models import CustomUser
from .services import complete_social_signup, create_user_profile, update_user_profile

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


class BaseAccountFormMixin:
    """Mixin base com campos e validadores comuns para forms de conta."""

    def _add_common_fields(self):
        """Adiciona campos comuns: cpf, telefone, endereço."""
        self.fields["cpf"] = forms.CharField(
            max_length=14,
            label="CPF",
            validators=[validate_brazilian_cpf],
            help_text="Usado para emitir cobranças.",
        )
        self.fields["telefone"] = forms.CharField(
            max_length=20,
            label="Telefone",
            help_text="Usado pelo gateway de pagamento.",
        )
        for name, field in _address_common_fields():
            self.fields[name] = field

    def clean_cpf(self):
        return _only_digits(self.cleaned_data.get("cpf"))

    def clean_telefone(self):
        return _only_digits(self.cleaned_data.get("telefone"))

    def clean_zip_code(self):
        return _only_digits(self.cleaned_data.get("zip_code"))


class RoleFieldMixin:
    """Mixin para campo role dinâmico baseado em SiteSettings."""

    def _add_role_field(self, initial=CustomUser.Role.CLIENTE):
        """Adiciona campo role com choices baseados nas configurações do site."""
        site_settings = SiteSettings.load()
        choices = [(CustomUser.Role.CLIENTE, "Cliente")]
        if site_settings.affiliates_enabled:
            choices.append((CustomUser.Role.AFILIADO, "Afiliado"))
        if site_settings.provider_registration_enabled:
            choices.append((CustomUser.Role.PRESTADOR, "Prestador"))
        self.fields["role"] = CustomUser._meta.get_field("role").formfield(
            choices=choices,
            initial=initial,
            label="Função",
            required=True,
        )

    def clean_role(self):
        role = self.cleaned_data.get("role")
        site_settings = SiteSettings.load()
        if (role == CustomUser.Role.PRESTADOR) and not site_settings.provider_registration_enabled:
            raise forms.ValidationError("O cadastro de prestadores está desabilitado.")
        if (role == CustomUser.Role.AFILIADO) and not site_settings.affiliates_enabled:
            raise forms.ValidationError("O cadastro de afiliados está desabilitado.")
        return role


class AddressFormMixin:
    """Mixin para upsert de endereço (create/update do primeiro ativo)."""

    def _upsert_address(self, user):
        """Cria ou atualiza o primeiro endereço ativo do usuário."""
        from apps.checkout.models import Address

        data = {field: self.cleaned_data[field] for field in _ADDRESS_FIELDS}
        address = user.addresses.filter(is_active=True).first()
        if address is None:
            Address.objects.create(user=user, **data)
        else:
            for field, value in data.items():
                setattr(address, field, value)
            address.save(update_fields=_ADDRESS_FIELDS)


class CustomSignupForm(BaseAccountFormMixin, RoleFieldMixin, forms.Form):
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
        self._add_role_field()
        self._add_common_fields()

    def signup(self, request, user):
        role = self.cleaned_data.get("role")
        is_provider = role == CustomUser.Role.PRESTADOR
        address_data = {
            "street": self.cleaned_data["street"],
            "number": self.cleaned_data["number"],
            "city": self.cleaned_data["city"],
            "state": self.cleaned_data["state"],
            "zip_code": self.cleaned_data["zip_code"],
            "country": self.cleaned_data["country"],
        }
        create_user_profile(
            user=user,
            role=role,
            cpf=self.cleaned_data["cpf"],
            telefone=self.cleaned_data["telefone"],
            address_data=address_data,
            is_provider_candidate=is_provider,
        )


class SocialSignupCompleteForm(BaseAccountFormMixin, RoleFieldMixin, forms.Form):
    """Completamento obrigatório após login social (Google)."""

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        self._add_role_field()
        self._add_common_fields()

    def save(self, user, sociallogin):
        """Atualiza usuário + cria Address + conecta SocialAccount."""
        complete_social_signup(user=user, form=self, request=self.request)
        return user


class ProfileEditForm(BaseAccountFormMixin, AddressFormMixin, forms.Form):
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
        self._add_common_fields()
        address = self.user.addresses.filter(is_active=True).first()
        self.fields["first_name"].initial = self.user.first_name
        self.fields["last_name"].initial = self.user.last_name
        self.fields["email"].initial = self.user.email
        self.fields["cpf"].initial = self.user.cpf
        self.fields["telefone"].initial = self.user.telefone
        if address is not None:
            for field in _ADDRESS_FIELDS:
                self.fields[field].initial = getattr(address, field)

    def save(self):
        data = {
            "first_name": self.cleaned_data.get("first_name") or "",
            "last_name": self.cleaned_data.get("last_name") or "",
            "cpf": self.cleaned_data["cpf"],
            "telefone": self.cleaned_data["telefone"],
            "street": self.cleaned_data["street"],
            "number": self.cleaned_data["number"],
            "city": self.cleaned_data["city"],
            "state": self.cleaned_data["state"],
            "zip_code": self.cleaned_data["zip_code"],
            "country": self.cleaned_data["country"],
        }
        update_user_profile(self.user, data)
