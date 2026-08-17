"""System checks do app core."""

from django.conf import settings
from django.core.checks import Error, register
from django.core.exceptions import ImproperlyConfigured


@register()
def check_secret_key(app_configs, **kwargs):
    """Valida SECRET_KEY em produção (DEBUG=False).

    Retorna erro se a chave for um valor inseguro conhecido.
    """
    errors = []
    if not settings.DEBUG:
        weak_keys = {
            "dev-insecure-change-me",
            "change-me-in-production",
        }
        try:
            secret_key = settings.SECRET_KEY
        except ImproperlyConfigured:
            # SECRET_KEY vazio ou não configurado
            errors.append(
                Error(
                    "SECRET_KEY não configurada em produção (DEBUG=False). "
                    "Defina DJANGO_SECRET_KEY no ambiente com valor aleatório forte.",
                    id="core.E001",
                )
            )
            return errors

        if secret_key in weak_keys or secret_key == "":
            errors.append(
                Error(
                    "SECRET_KEY insegura em produção (DEBUG=False). "
                    "Defina DJANGO_SECRET_KEY no ambiente com valor aleatório forte.",
                    id="core.E001",
                )
            )
    return errors
