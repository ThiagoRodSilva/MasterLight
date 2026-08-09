"""Admin do app core (configurações do site)."""

from django.contrib import admin

from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """Painel de configuração do site (singleton)."""

    list_display = (
        "store_enabled",
        "services_enabled",
        "affiliates_enabled",
        "maintenance_enabled",
        "provider_registration_enabled",
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # O registro único já existe (seed via migration); impede criar outro.
        return False

    def has_delete_permission(self, request, obj=None):
        return False
