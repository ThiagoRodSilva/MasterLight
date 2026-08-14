"""System checks do app payments: configuracao do provedor de pagamento."""

from django.conf import settings
from django.core.checks import Error, register


@register()
def asaas_api_key_check(app_configs, **kwargs):
    """Falha cedo no `manage.py check` quando o Asaas esta ativo sem chave.

    Sem isso a configuracao errada so aparece como 500 na primeira chamada a
    API (charge/subscribe/webhook). Em testes o provider e 'manual' e a chave
    vazia, entao o check nao dispara.
    """
    if settings.PAYMENT_PROVIDER != "asaas" or settings.ASAAS_API_KEY:
        return []
    return [
        Error(
            "ASAAS_API_KEY não configurada com PAYMENT_PROVIDER=asaas.",
            hint=(
                "Defina ASAAS_API_KEY no .env ou nas env vars do ambiente "
                "(ex.: Vercel). Valores que começam com '$' são lidos como "
                "referência a outra env var pelo django-environ — a chave crua "
                "'$aact_...' é suportada."
            ),
            obj="settings.ASAAS_API_KEY",
            id="payments.E001",
        )
    ]
