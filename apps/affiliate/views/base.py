"""Mixin base para views de afiliado."""

from django.db.models import ObjectDoesNotExist
from django.http import Http404

from apps.core.mixins import AffiliateRequiredMixin, SectionEnabledMixin


class AffiliateBaseMixin(AffiliateRequiredMixin, SectionEnabledMixin):
    """Mixin base com funcionalidades comuns para views de afiliado."""

    section_flag = "affiliates_enabled"

    def get_profile(self):
        """Retorna o AffiliateProfile do usuário atual ou 404."""
        try:
            return self.request.user.affiliate_profile
        except ObjectDoesNotExist as exc:
            raise Http404("Perfil de afiliado não encontrado.") from exc

    def get_ref_url(self, profile=None):
        """Gera URL de indicação com o código do afiliado."""
        profile = profile or self.get_profile()
        return self.request.build_absolute_uri(f"/?ref={profile.code}")
