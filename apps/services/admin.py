from django.contrib import admin

from .models import (
    Service,
    ServiceCategory,
    ServiceRequest,
)


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon", "is_active")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "base_price", "created_by", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name",)
    filter_horizontal = ("providers",)


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "service",
        "cliente",
        "prestador",
        "status",
        "final_price",
        "created_at",
    )
    list_filter = ("status", "service__category")
    search_fields = ("cliente__email", "prestador__email", "service__name", "address")
    date_hierarchy = "created_at"
