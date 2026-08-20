"""Views do app affiliate."""

from .base import AffiliateBaseMixin
from .dashboard import AffiliateDashboardView
from .landing import AffiliateLandingView
from .payout import PayoutRequestView
from .pix_key import PixKeyUpdateView

__all__ = [
    "AffiliateBaseMixin",
    "AffiliateLandingView",
    "AffiliateDashboardView",
    "PayoutRequestView",
    "PixKeyUpdateView",
]
