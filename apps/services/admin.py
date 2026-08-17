from django.contrib import admin

from .models import (
    MaintenancePlan,
    MaintenancePlanTemplate,
    MaintenanceVisit,
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


class MaintenanceVisitInline(admin.TabularInline):
    model = MaintenanceVisit
    extra = 0
    fields = ("scheduled_at", "completed_at", "notes", "is_active")


@admin.register(MaintenancePlan)
class MaintenancePlanAdmin(admin.ModelAdmin):
    list_display = (
        "client",
        "plan_type",
        "value",
        "next_due_date",
        "prestador",
        "is_active",
        "created_at",
    )
    list_filter = ("plan_type", "is_active")
    search_fields = ("client__email", "prestador__email", "asaas_subscription_id")
    date_hierarchy = "created_at"
    autocomplete_fields = ("client", "prestador")
    readonly_fields = ("asaas_subscription_id",)
    inlines = (MaintenanceVisitInline,)


@admin.register(MaintenancePlanTemplate)
class MaintenancePlanTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "plan_type",
        "value",
        "ordering",
        "is_active",
        "updated_at",
    )
    list_editable = ("value", "ordering", "is_active")
    list_filter = ("plan_type", "is_active")
    search_fields = ("name", "description")
    ordering = ("ordering", "value")


@admin.register(MaintenanceVisit)
class MaintenanceVisitAdmin(admin.ModelAdmin):
    list_display = ("plan", "scheduled_at", "completed_at", "is_active", "created_at")
    list_filter = ("completed_at", "plan__plan_type")
    search_fields = ("plan__client__email", "notes")
    date_hierarchy = "scheduled_at"
