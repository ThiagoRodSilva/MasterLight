"""Admin programa afiliados."""

from django.contrib import admin
from django.db import transaction as db_transaction
from django.utils import timezone

from .models import AffiliateProfile, PayoutRequest, Referral


class ReferralInline(admin.TabularInline):
    model = Referral
    extra = 0
    readonly_fields = ("status", "commission_amount", "referred", "order", "created_at")
    can_delete = False
    show_change_link = True


@admin.register(AffiliateProfile)
class AffiliateProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "code", "commission_rate", "balance", "is_active")
    search_fields = ("code", "user__email")
    readonly_fields = ("code",)
    date_hierarchy = "created_at"
    inlines = [ReferralInline]


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ("affiliate", "referred", "order", "status", "commission_amount")
    list_filter = ("status",)
    date_hierarchy = "created_at"


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = ("affiliate", "amount", "status", "paid_at")
    list_filter = ("status",)
    date_hierarchy = "created_at"
    actions = ["approve_payout", "execute_payout"]

    @admin.action(description="Aprovar saques selecionados")
    def approve_payout(self, request, queryset):
        """Marca saques pendentes como aprovados (status permanece PENDING neste fluxo manual)."""
        qs = queryset.filter(status=PayoutRequest.Status.PENDING)
        count = qs.count()
        if count == 0:
            self.message_user(request, "Nenhum saque pendente selecionado.", level="warning")
            return
        self.message_user(request, f"{count} saque(s) pronto(s) para execução manual.")

    @admin.action(description="Efetuar saques (marcar como pagos)")
    def execute_payout(self, request, queryset):
        """Efetua saque: marca status PAID e registra paid_at atomicamente."""
        qs = queryset.filter(status=PayoutRequest.Status.PENDING)
        with db_transaction.atomic():
            count = qs.update(status=PayoutRequest.Status.PAID, paid_at=timezone.now())
        if count == 0:
            self.message_user(request, "Nenhum saque pendente selecionado.", level="warning")
        else:
            self.message_user(request, f"{count} saque(s) efetuado(s).")
