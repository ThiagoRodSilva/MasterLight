from django.contrib import admin, messages

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("order", "provider", "external_id", "amount", "status", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("external_id", "order__id")
    date_hierarchy = "created_at"
    actions = ["sync_pending_with_asaas"]

    @admin.action(description="Sincronizar status pendentes com o Asaas")
    def sync_pending_with_asaas(self, request, queryset):
        from .management.commands.sync_payments import _ASAAS_TO_LOCAL
        from .services import AsaasGateway

        gateway = AsaasGateway()
        updated = 0
        for tx in queryset.filter(
            provider="asaas",
            status=Transaction.Status.PENDING,
            kind=Transaction.Kind.PAYMENT,
            external_id__gt="",
        ).order_by("-created_at"):
            try:
                data = gateway.fetch_payment(tx.external_id)
            except ValueError:
                continue
            new_status = _ASAAS_TO_LOCAL.get(str(data.get("status") or "").lower())
            if new_status is None or new_status == tx.status:
                continue
            tx.status = new_status
            tx.save(update_fields=["status", "updated_at"])
            updated += 1
        messages.success(request, f"{updated} transações atualizadas.")
