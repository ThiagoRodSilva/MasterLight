"""Middleware para bloquear acesso se cadastro social incompleto."""

from django.shortcuts import redirect
from django.urls import resolve
from django.contrib.auth import get_user_model

User = get_user_model()

EXEMPT_URLS = {
    "account_logout",
    "social_signup_complete",
    "account_login",
    "account_signup",
    "password_reset",
    "password_reset_done",
    "password_reset_confirm",
    "password_reset_complete",
    "home",
    "socialaccount_login",
    "socialaccount_signup",
    "socialaccount_connections",
    "accounts-me",
    "accounts-me-edit",
    "accounts-profile",
}


class SocialSignupRequiredMiddleware:
    """Redireciona usuário autenticado sem CPF/telefone/endereço para completamento."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_superuser:
            # Verifica se perfil está incompleto
            incomplete = not (
                request.user.cpf
                and request.user.telefone
                and request.user.addresses.filter(is_active=True).exists()
            )
            if incomplete:
                try:
                    current_url = resolve(request.path_info).url_name
                except Exception:
                    current_url = None
                if current_url not in EXEMPT_URLS and not (current_url and current_url.startswith("admin:")):
                    return redirect("social_signup_complete")

        return self.get_response(request)