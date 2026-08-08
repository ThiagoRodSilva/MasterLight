"""Views programa afiliados."""

from django.contrib import messages
from django.db.models import ObjectDoesNotExist
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import ListView, TemplateView, View

from apps.core.mixins import AffiliateRequiredMixin, SectionEnabledMixin

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

    def get_profile(self):
        try:
            return self.request.user.affiliate_profile
        except ObjectDoesNotExist as exc:
            raise Http404("Perfil de afiliado não encontrado.") from exc

    def get_queryset(self):
        profile = self.get_profile()
        return (
            Referral.objects.filter(affiliate=profile)
            .select_related("order", "referred")
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = self.get_profile()
        ctx["profile"] = profile
        ctx["payouts"] = PayoutRequest.objects.filter(affiliate=profile)
        ctx["ref_url"] = self.request.build_absolute_uri(f"/?ref={profile.code}")
        return ctx


class PayoutRequestView(SectionEnabledMixin, AffiliateRequiredMixin, View):
    """Solicita saque (POST), protegido para afiliados/admin."""

    section_flag = "affiliates_enabled"

    def post(self, request):
        try:
            profile = request.user.affiliate_profile
        except ObjectDoesNotExist as exc:
            raise Http404("Perfil de afiliado não encontrado.") from exc
        try:
            create_payout_request(profile)
        except ValueError:
            messages.error(request, "Saldo insuficiente para saque.")
        else:
            messages.success(request, "Solicitação de saque criada.")
        return redirect("affiliate-dashboard")

    def get(self, request):
        return redirect("affiliate-dashboard")
