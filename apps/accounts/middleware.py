"""Middleware para bloquear acesso se cadastro social incompleto."""

from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import resolve

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
    "checkout-cart",
    "checkout-cart-add",
    "checkout-cart-remove",
    "checkout",
    "checkout-address",
    "affiliate-landing",
    "affiliate-dashboard",
    "affiliate-pix-key",
    "affiliate-payout",
    "services-list",
    "services-detail",
    "services-create",
    "services-my",
    "services-update",
    "services-delete",
    "services-request",
    "services-my-requests",
    "services-provider-requests",
    "services-request-quote",
    "services-request-approve",
    "services-request-paylink",
    "services-request-cancel",
    "services-plan-list",
    "services-plan-subscribe",
    "services-visits",
    "services-visit-complete",
    "portfolio-list",
    "portfolio-detail",
    "portfolio-create",
    "portfolio-update",
}


class SocialSignupRequiredMiddleware:
    """Redireciona usuário autenticado sem CPF/telefone/endereço para completamento.

    Aplica-se apenas a usuários que se cadastraram via login social (allauth),
    identificados pela existência de SocialAccount associada.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_superuser:
            # Só bloqueia usuários que vieram de login social (têm SocialAccount)
            from allauth.socialaccount.models import SocialAccount
            has_social_account = SocialAccount.objects.filter(user=request.user).exists()

            if has_social_account:
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
