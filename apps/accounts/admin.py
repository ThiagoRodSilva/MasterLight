"""Admin de CustomUser."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, PublicProfile


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
