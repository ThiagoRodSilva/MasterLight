"""Middleware que grava o cookie de afiliado a partir do parametro `?ref=`.

Quando um visitante chega com `?ref=CODE`, o codigo valido e persistido no
cookie (30 dias) para ser lido no checkout e gerar a Referral.
"""

from django.conf import settings

from .models import AffiliateProfile


class AffiliateReferralMiddleware:
    """Le `?ref=CODE` e seta/renova o cookie `ref` so para codigos validos."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ref_code = request.GET.get("ref")
        if ref_code:
            valid = AffiliateProfile.objects.filter(
                code=ref_code, is_active=True
            ).exists()
            if valid:
                max_age = getattr(settings, "AFFILIATE_COOKIE_MAX_AGE", 30 * 24 * 60 * 60)
                request._affiliate_ref_valid = True
                response = self.get_response(request)
                response.set_cookie(
                    settings.AFFILIATE_COOKIE_NAME,
                    ref_code,
                    max_age=max_age,
                    httponly=True,
                    samesite="Lax",
                )
                return response
        return self.get_response(request)
