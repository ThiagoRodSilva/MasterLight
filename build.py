"""Build command da Vercel ([tool.vercel.scripts] build).

Roda com as env vars do projeto (DATABASE_URL, sociais). Migrate,
bootstrap_social e check sao idempotentes: seguros em todo deploy.
"""

import os

import django


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.vercel")
    django.setup()

    from django.core.management import call_command

    # `check` falha o deploy cedo se a configuracao estiver quebrada (ex.:
    # payments.E001 com PAYMENT_PROVIDER=asaas sem ASAAS_API_KEY), em vez de
    # virar 500 em runtime.
    call_command("check")
    call_command("migrate", "--noinput")
    call_command("bootstrap_social")


if __name__ == "__main__":
    main()
