"""View de solicitação de saque."""

from django.contrib import messages
from django.shortcuts import redirect
from django.views import View

from ..services import create_payout_request
from .base import AffiliateBaseMixin


class PayoutRequestView(AffiliateBaseMixin, View):
    """Solicita saque (POST), protegido para afiliados/admin."""

    def post(self, request):
        profile = self.get_profile()
        try:
            create_payout_request(profile)
        except ValueError as exc:
            messages.error(request, str(exc) or "Saldo insuficiente para saque.")
        else:
            messages.success(request, "Solicitação de saque criada.")
        return redirect("affiliate-dashboard")

    def get(self, request):
        return redirect("affiliate-dashboard")
