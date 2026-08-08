from django.contrib import admin

from .models import Address, Order, OrderItem


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("user", "street", "city", "state", "zip_code")
    search_fields = ("street", "city", "user__email")
    date_hierarchy = "created_at"


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("line_total",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "kind", "status", "total", "created_at")
    list_filter = ("status", "kind")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]
