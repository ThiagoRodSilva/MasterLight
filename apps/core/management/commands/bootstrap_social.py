"""Management command para bootstrap site + SocialApp a partir do .env."""

from django.core.management.base import BaseCommand

from apps.core.social_bootstrap import bootstrap_site, bootstrap_social_apps


class Command(BaseCommand):
    help = "Cria/atualiza Site e SocialApp (Google/Facebook) com base no .env."

    def handle(self, *args, **options):
        bootstrap_site()
        bootstrap_social_apps()
        self.stdout.write(self.style.SUCCESS("Site SocialApp sincronizados."))
