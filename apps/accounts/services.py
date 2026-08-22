"""Business logic de contas: aprovação de prestadores, criação/atualização de perfis."""

from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.db import transaction
from django.utils import timezone

from apps.checkout.models import Address
from apps.core.models import SiteSettings

from .models import CustomUser, ProviderApplication, PublicProfile


def create_user_profile(
    user: CustomUser,
    role: str,
    cpf: str,
    telefone: str,
    address_data: dict,
    is_provider_candidate: bool = False,
) -> CustomUser:
    """Cria perfil completo do usuário (CPF, telefone, endereço, role).

    Usado tanto no signup normal quanto no completamento social.
    """
    with transaction.atomic():
        user.cpf = cpf
        user.telefone = telefone

        if is_provider_candidate:
            # Candidato a prestador: mantém role=cliente até aprovação
            user.role = CustomUser.Role.CLIENTE
            user.save(update_fields=["role", "cpf", "telefone"])
            ProviderApplication.objects.create(user=user)
        else:
            user.role = role if role == CustomUser.Role.AFILIADO else CustomUser.Role.CLIENTE
            user.save(update_fields=["role", "cpf", "telefone"])

        Address.objects.create(user=user, **address_data)

    return user


def update_user_profile(user: CustomUser, data: dict) -> CustomUser:
    """Atualiza dados pessoais e endereço do usuário (upsert)."""
    _ADDRESS_FIELDS = ["street", "number", "city", "state", "zip_code", "country"]

    with transaction.atomic():
        user.first_name = data.get("first_name") or ""
        user.last_name = data.get("last_name") or ""
        user.cpf = data["cpf"]
        user.telefone = data["telefone"]
        user.save(update_fields=["first_name", "last_name", "cpf", "telefone"])

        address_data = {field: data[field] for field in _ADDRESS_FIELDS}
        address = user.addresses.filter(is_active=True).first()
        if address is None:
            Address.objects.create(user=user, **address_data)
        else:
            for field, value in address_data.items():
                setattr(address, field, value)
            address.save(update_fields=_ADDRESS_FIELDS)

    return user


def complete_social_signup(user: CustomUser, form, request) -> CustomUser:
    """Completa cadastro após login social: atualiza usuário, cria endereço, conecta SocialAccount."""
    sociallogin_data = request.session.pop("sociallogin", None)
    if sociallogin_data is None:
        raise ValueError("sociallogin não encontrado na sessão")
    sociallogin = SocialLogin.deserialize(sociallogin_data)

    with transaction.atomic():
        user.cpf = form.cleaned_data["cpf"]
        user.telefone = form.cleaned_data["telefone"]
        role = form.cleaned_data.get("role")

        settings = SiteSettings.load()
        if role == CustomUser.Role.PRESTADOR and not settings.provider_registration_enabled:
            role = CustomUser.Role.CLIENTE
        if role == CustomUser.Role.AFILIADO and not settings.affiliates_enabled:
            role = CustomUser.Role.CLIENTE
        user.role = role
        user.save(update_fields=["cpf", "telefone", "role"])

        Address.objects.create(
            user=user,
            street=form.cleaned_data["street"],
            number=form.cleaned_data["number"],
            city=form.cleaned_data["city"],
            state=form.cleaned_data["state"],
            zip_code=form.cleaned_data["zip_code"],
            country=form.cleaned_data["country"],
        )

        # Conecta SocialAccount definitivamente
        sociallogin.user = user
        social_account = getattr(sociallogin, "account", None)
        if social_account is not None:
            existing_account = SocialAccount.objects.filter(
                user=user,
                provider=social_account.provider,
                uid=social_account.uid,
            ).first()
            if existing_account:
                sociallogin.account = existing_account
        sociallogin.connect(request, user)

    return user


def approve_provider_application(application: ProviderApplication, admin) -> None:
    """Aprova a solicitação e promove o usuário a prestador.

    Levanta ValueError para fluxos inválidos (solicitação inexistente
    ou usuário desativado).
    """
    if not application.is_pending:
        raise ValueError("A solicitação já foi analisada.")
    user = application.user
    if not user.is_active:
        raise ValueError("O usuário não pode ser aprovado com a conta desativada.")
    user.role = CustomUser.Role.PRESTADOR
    user.save(update_fields=["role"])
    PublicProfile.objects.get_or_create(user=user)
    application.status = ProviderApplication.Status.APPROVED
    application.reviewed_by = admin
    application.reviewed_at = timezone.now()
    application.save(update_fields=["status", "reviewed_by", "reviewed_at"])


def reject_provider(application: ProviderApplication, admin) -> None:
    """Recusa a solicitação; o usuário permanece como cliente."""
    if not application.is_pending:
        raise ValueError("A solicitação já foi analisada.")
    application.status = ProviderApplication.Status.REJECTED
    application.reviewed_by = admin
    application.reviewed_at = timezone.now()
    application.save(update_fields=["status", "reviewed_by", "reviewed_at"])


def promote_to_provider(user: CustomUser, admin) -> None:
    """Promove usuário a prestador (cria PublicProfile)."""
    if user.role == CustomUser.Role.PRESTADOR:
        return
    user.role = CustomUser.Role.PRESTADOR
    user.save(update_fields=["role"])
    PublicProfile.objects.get_or_create(user=user)


def demote_from_provider(user: CustomUser) -> None:
    """Rebaixa usuário de prestador para cliente (mantém PublicProfile ativo por decisão de design)."""
    if user.role == CustomUser.Role.PRESTADOR:
        user.role = CustomUser.Role.CLIENTE
        user.save(update_fields=["role"])
        # PublicProfile NÃO é desativado/deletado (decisão de design: preserva histórico)
