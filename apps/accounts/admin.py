"""Admin de CustomUser."""

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, ProviderApplication, PublicProfile
from .services import approve_provider_application, reject_provider

APPROVAL_ACTIONS_DESCRIPTION = "Aprovar/recusar solicitações de prestador"


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "username", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "username", "telefone", "cpf")
    date_hierarchy = "date_joined"
    fieldsets = UserAdmin.fieldsets + (
        ("Extra", {"fields": ("role", "telefone", "cpf", "avatar")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Extra", {"fields": ("role", "telefone", "cpf", "avatar")}),
    )


@admin.register(PublicProfile)
class PublicProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "website", "is_active")
    search_fields = ("user__email",)
    date_hierarchy = "created_at"


@admin.register(ProviderApplication)
class ProviderApplicationAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "bio", "created_at", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("user__email", "user__username")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at", "reviewed_at")
    actions = ("approve_selected", "reject_selected")
    actions_description = APPROVAL_ACTIONS_DESCRIPTION

    @admin.action(description="Aprovar solicitações selecionadas")
    def approve_selected(self, request, queryset):
        count = 0
        for application in queryset:
            try:
                approve_provider_application(application, request.user)
            except ValueError as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
                continue
            count += 1
        if count:
            self.message_user(
                request,
                f"{count} solicitação(ões) aprovada(s) e prestador(es) habilitado(s).",
            )

    @admin.action(description="Recusar solicitações selecionadas")
    def reject_selected(self, request, queryset):
        count = 0
        for application in queryset.filter(status=ProviderApplication.Status.PENDING):
            reject_provider(application, request.user)
            count += 1
        if count:
            self.message_user(request, f"{count} solicitação(ões) recusada(s).")
