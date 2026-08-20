"""View da landing page pública de afiliados."""

from django.views.generic import TemplateView

from apps.core.mixins import SectionEnabledMixin


class AffiliateLandingView(SectionEnabledMixin, TemplateView):
    """Landing pública explicando o programa de afiliados."""

    section_flag = "affiliates_enabled"
    template_name = "affiliate/landing.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_authenticated and hasattr(user, "affiliate_profile"):
            profile = user.affiliate_profile
            ctx["ref_url"] = self.request.build_absolute_uri(f"/?ref={profile.code}")
            ctx["profile"] = profile
        return ctx
