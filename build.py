"""Build command da Vercel ([tool.vercel.scripts] build).

Roda com as env vars do projeto (DATABASE_URL, R2, sociais). Migrate e
bootstrap_social sao idempotentes: seguros em todo deploy.
"""

import os

import django


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.vercel")
    django.setup()

    from django.core.management import call_command

    call_command("migrate", "--noinput")
    call_command("bootstrap_social")


if __name__ == "__main__":
    main()
