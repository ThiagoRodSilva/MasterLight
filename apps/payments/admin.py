from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("order", "provider", "external_id", "amount", "status", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("external_id", "order__id")
    date_hierarchy = "created_at"
