"""Mixins reutilizaveis para views."""

from typing import Any, ClassVar

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.http import Http404

from apps.accounts.models import CustomUser

from .models import SiteSettings


class SectionEnabledMixin:
    """Bloqueia a view (404) quando a seção está desabilitada no Admin.

    Defina `section_flag` no subtipo:
        SectionEnabledMixin.section_flag = "services_enabled"
    """

    section_flag: ClassVar[str] = "services_enabled"

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        if not getattr(SiteSettings.load(), self.section_flag, True):
            raise Http404("Seção indisponível no momento.")
        return super().dispatch(request, *args, **kwargs)


class RoleRequiredMixin(LoginRequiredMixin):
    """Base dos mixins de separação de contas.

    Permite apenas usuários cuja `role` esteja em `allowed_roles`, além de
    admins (`role=CustomUser.Role.ADMIN`) e superusers — os únicos com acesso a tudo.
    """

    allowed_roles: ClassVar[set[str]] = set()

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        user = request.user
        if not user.is_authenticated:
            return self.handle_no_permission()
        if not (user.is_superuser or user.role in self.allowed_roles):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class OwnerRequiredMixin(LoginRequiredMixin):
    """Garante que o objeto pertence ao usuário autenticado.

    Admins/superusers (acesso a tudo) enxergam todos os objetos.
    """

    def get_queryset(self) -> QuerySet[Any]:
        qs = super().get_queryset()
        if self.request.user.is_admin:
            return qs
        return qs.filter(created_by=self.request.user)


class ProviderRequiredMixin(RoleRequiredMixin):
    """Limita acesso a prestadores/admin."""

    allowed_roles: ClassVar[set[str]] = {CustomUser.Role.PRESTADOR, CustomUser.Role.ADMIN}


class AffiliateRequiredMixin(RoleRequiredMixin):
    """Limita acesso a afiliados/admin."""

    allowed_roles: ClassVar[set[str]] = {CustomUser.Role.AFILIADO, CustomUser.Role.ADMIN}


class ClienteRequiredMixin(RoleRequiredMixin):
    """Limita acesso a clientes/admin (ex.: solicitar orçamento de serviço)."""

    allowed_roles: ClassVar[set[str]] = {CustomUser.Role.CLIENTE, CustomUser.Role.ADMIN}
