"""Inicializacao de SocialApp para dev/prod a partir de variaveis de ambiente."""

import os

from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site


def bootstrap_social_apps():
    """Cria/atualiza SocialApp para Google/Facebook usando env se disponivel.

    Executado via `apps/payments`? Nao - chamado por AppConfig do core em ready
    somente quando variaveis existirem. Apple fica fora por exigir chave privada.
    """
    providers = {
        "google": ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
        "facebook": ("FACEBOOK_CLIENT_ID", "FACEBOOK_CLIENT_SECRET"),
    }
    site = Site.objects.filter(id=1).first()
    if not site:
        return
    for provider, (id_var, secret_var) in providers.items():
        client_id = os.getenv(id_var, "")
        secret = os.getenv(secret_var, "")
        if not client_id or not secret:
            continue
        app, _ = SocialApp.objects.get_or_create(provider=provider)
        app.client_id = client_id
        app.secret = secret
        app.name = provider.capitalize()
        app.save()
        app.sites.add(site)


def bootstrap_site():
    """Garante site id=1 com dominio configurado via env."""
    domain = os.getenv("DJANGO_SITE_DOMAIN", "localhost:8000")
    name = os.getenv("DJANGO_SITE_NAME", "PlataformaVendas")
    Site.objects.update_or_create(id=1, defaults={"domain": domain, "name": name})
