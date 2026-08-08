from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"

    def ready(self) -> None:
        # Importa sinais de accounts para que sejam conectados ao startup.
        from apps.accounts import signals  # noqa: F401
