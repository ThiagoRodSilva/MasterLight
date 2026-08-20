"""View de cadastro/atualização da chave Pix."""

from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import FormView

from ..forms import PixKeyForm
from .base import AffiliateBaseMixin


class PixKeyUpdateView(AffiliateBaseMixin, FormView):
    """Cadastra/atualiza a chave Pix do afiliado para recebimento de saques."""

    form_class = PixKeyForm
    success_url = "/afiliados/painel/"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_profile()
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Chave Pix cadastrada com sucesso.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Verifique a chave Pix informada.")
        return redirect("affiliate-dashboard")
