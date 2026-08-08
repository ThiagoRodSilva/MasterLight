"""Mixins reutilizaveis para views."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404

from .models import SiteSettings


class SectionEnabledMixin:
    """Bloqueia a view (404) quando a seção está desabilitada no Admin.

    Defina `section_flag` no subtipo:
        SectionEnabledMixin.section_flag = "store_enabled"
    """

    section_flag = "store_enabled"

    def dispatch(self, request, *args, **kwargs):
        if not getattr(SiteSettings.load(), self.section_flag, True):
            raise Http404("Seção indisponível no momento.")
        return super().dispatch(request, *args, **kwargs)


class OwnerRequiredMixin(LoginRequiredMixin):
    """Garante que o objeto pertence ao usuario autenticado."""

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(created_by=self.request.user)


class ProviderRequiredMixin(LoginRequiredMixin):
    """Limita acesso a prestadores/admin."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role not in ("prestador", "admin"):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class AffiliateRequiredMixin(LoginRequiredMixin):
    """Limita acesso afiliados/admin."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role not in ("afiliado", "admin"):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class ClienteRequiredMixin(LoginRequiredMixin):
    """Limita acesso clientes/admin (ex.: solicitar orçamento de serviço)."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role not in ("cliente", "admin"):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
