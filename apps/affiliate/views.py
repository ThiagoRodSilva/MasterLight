"""Views programa afiliados."""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import ListView, TemplateView

from apps.core.mixins import AffiliateRequiredMixin, SectionEnabledMixin
from apps.core.models import SiteSettings

from .models import PayoutRequest, Referral
from .services import create_payout_request


class AffiliateLandingView(SectionEnabledMixin, TemplateView):
    """Landing pública explicando o programa de afiliados."""

    section_flag = "affiliates_enabled"
    template_name = "affiliate/landing.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_authenticated and hasattr(user, "affiliate_profile"):
            ctx["ref_url"] = self.request.build_absolute_uri(f"/?ref={user.affiliate_profile.code}")
            ctx["profile"] = user.affiliate_profile
        return ctx


class AffiliateDashboardView(SectionEnabledMixin, AffiliateRequiredMixin, ListView):
    section_flag = "affiliates_enabled"
    template_name = "affiliate/dashboard.html"
    context_object_name = "referrals"
    paginate_by = 20

    def get_queryset(self):
        profile = self.request.user.affiliate_profile
        return Referral.objects.filter(affiliate=profile).select_related(
            "order", "referred"
        ).order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = self.request.user.affiliate_profile
        ctx["profile"] = profile
        ctx["payouts"] = PayoutRequest.objects.filter(affiliate=profile)
        ctx["ref_url"] = self.request.build_absolute_uri(f"/?ref={profile.code}")
        return ctx


def request_payout(request):
    if not SiteSettings.load().affiliates_enabled:
        raise Http404("Seção indisponível no momento.")
    if request.method != "POST":
        return redirect("affiliate-dashboard")
    try:
        create_payout_request(request.user.affiliate_profile)
    except ValueError:
        messages.error(request, "Saldo insuficiente para saque.")
    else:
        messages.success(request, "Solicitação de saque criada.")
    return redirect("affiliate-dashboard")
