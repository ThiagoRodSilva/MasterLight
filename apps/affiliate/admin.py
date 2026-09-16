"""Admin programa afiliados."""

from django.contrib import admin
from django.db import transaction as db_transaction
from django.utils import timezone

from .models import AffiliateProfile, PayoutRequest, Referral


class ReferralInline(admin.TabularInline):
    model = Referral
    extra = 0
    readonly_fields = (
        "status",
        "commission_amount",
        "commission_rate",
        "referred",
        "order",
        "created_at",
    )
    can_delete = False
    show_change_link = True


@admin.register(AffiliateProfile)
class AffiliateProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "code", "pix_key", "commission_rate", "balance", "is_active")
    search_fields = ("code", "user__email")
    readonly_fields = ("code", "created_at", "updated_at")
    date_hierarchy = "created_at"
    inlines = [ReferralInline]


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = (
        "affiliate",
        "referred",
        "order",
        "status",
        "commission_amount",
        "commission_rate",
    )
    list_filter = ("status",)
    date_hierarchy = "created_at"
    readonly_fields = ("commission_rate", "commission_amount", "created_at", "updated_at")
    raw_id_fields = ("affiliate", "referred", "order")


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = ("affiliate", "amount", "status", "paid_at", "created_at")
    list_filter = ("status",)
    date_hierarchy = "created_at"
    actions = ["approve_payout", "execute_payout", "reject_payout"]
    readonly_fields = ("created_at", "updated_at", "paid_at")

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

    @admin.action(description="Rejeitar saques selecionados")
    def reject_payout(self, request, queryset):
        """Rejeita saques pendentes: devolve valor ao saldo do afiliado."""
        from decimal import Decimal

        qs = queryset.filter(status=PayoutRequest.Status.PENDING)
        count = 0
        with db_transaction.atomic():
            for payout in qs.select_for_update():
                affiliate = payout.affiliate
                affiliate.balance = (affiliate.balance or Decimal("0")) + payout.amount
                affiliate.save(update_fields=["balance", "updated_at"])
                payout.status = PayoutRequest.Status.REJECTED
                payout.save(update_fields=["status", "updated_at"])
                count += 1
        if count == 0:
            self.message_user(request, "Nenhum saque pendente selecionado.", level="warning")
        else:
            self.message_user(request, f"{count} saque(s) rejeitado(s) — valor devolvido ao saldo.")
