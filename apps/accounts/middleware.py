"""Middleware para bloquear acesso se cadastro social incompleto."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import Resolver404, resolve

User = get_user_model()


class SocialSignupRequiredMiddleware:
    """Redireciona usuário autenticado sem CPF/telefone/endereço para completamento.

    Aplica-se apenas a usuários que se cadastraram via login social (allauth),
    identificados pela existência de SocialAccount associada.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Carrega URLs isentas das settings (com fallback para lista hardcoded)
        self.exempt_urls = set(getattr(settings, "SOCIAL_SIGNUP_EXEMPT_URLS", []))

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_superuser:
            # Só bloqueia usuários que vieram de login social (têm SocialAccount)
            from allauth.socialaccount.models import SocialAccount
            has_social_account = SocialAccount.objects.filter(user=request.user).exists()

            if has_social_account:
                # Verifica se perfil está incompleto usando método do modelo
                if not request.user.has_complete_payment_profile():
                    is_exempt = False
                    # Primeiro verifica path direto para admin (mais confiável)
                    if request.path_info.startswith("/admin/"):
                        is_exempt = True
                    else:
                        try:
                            current_url = resolve(request.path_info).url_name
                            is_exempt = (
                                current_url in self.exempt_urls
                                or (current_url and current_url.startswith("admin:"))
                            )
                        except Resolver404:
                            is_exempt = False

                    if not is_exempt:
                        return redirect("social_signup_complete")

        return self.get_response(request)
