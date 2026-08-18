"""Adapters customizados para django-allauth."""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url

User = get_user_model()


class CustomAccountAdapter(DefaultAccountAdapter):
    """Adapter para cadastro/login por email/senha."""

    def get_login_redirect_url(self, request):
        return resolve_url("home")

    def get_signup_redirect_url(self, request):
        return resolve_url("home")


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Adapter para login social (Google)."""

    def is_auto_signup_allowed(self, request, sociallogin: SocialLogin) -> bool:
        """Força tela de completamento — nunca auto-signup direto."""
        return False

    def pre_social_login(self, request, sociallogin: SocialLogin) -> None:
        """Vincula conta existente por email ou prepara novo usuário."""
        email = sociallogin.user.email
        if not email:
            return

        # Usuário já existe? Conecta a SocialAccount
        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user:
            sociallogin.connect(request, existing_user)
            return

        # Novo usuário: guarda sociallogin na sessão para completamento
        request.session["sociallogin"] = sociallogin.serialize()

    def save_user(self, request, sociallogin: SocialLogin, form=None) -> User:
        """Cria usuário base (sem CPF/telefone/endereço/role — virão no completamento)."""
        user = super().save_user(request, sociallogin, form)
        # role padrão = cliente; CPF/telefone/endereço = vazios
        user.role = User.Role.CLIENTE
        user.save(update_fields=["role"])
        return user

    def get_signup_redirect_url(self, request):
        """Redireciona para tela de completamento obrigatório."""
        return resolve_url("social_signup_complete")