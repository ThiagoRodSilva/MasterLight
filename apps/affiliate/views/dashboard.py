"""View do dashboard do afiliado."""

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.views.generic import ListView

from ..models import PayoutRequest, Referral
from .base import AffiliateBaseMixin


class AffiliateDashboardView(AffiliateBaseMixin, ListView):
    """Dashboard do afiliado com indicações e saques."""

    template_name = "affiliate/dashboard.html"
    context_object_name = "referrals"
    paginate_by = 20

    def get_queryset(self):
        profile = self.get_profile()
        return (
            Referral.objects.active()
            .filter(affiliate=profile)
            .select_related("order", "referred")
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = self.get_profile()
        ctx["profile"] = profile
        ctx["ref_url"] = self.get_ref_url(profile)

        # Total de indicações (não apenas a página atual)
        ctx["referral_count"] = Referral.objects.active().filter(affiliate=profile).count()

        # Saques paginados (20 por página)
        payouts_qs = (
            PayoutRequest.objects.active().filter(affiliate=profile).order_by("-created_at")
        )
        paginator = Paginator(payouts_qs, 20)
        page = self.request.GET.get("payout_page", 1)
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)
        ctx["payouts_page"] = page_obj
        ctx["payouts"] = page_obj.object_list

        return ctx
