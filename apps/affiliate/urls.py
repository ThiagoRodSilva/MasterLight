from django.urls import path

from .views import (
    AffiliateDashboardView,
    AffiliateLandingView,
    PayoutRequestView,
    PixKeyUpdateView,
)

urlpatterns = [
    path("", AffiliateLandingView.as_view(), name="affiliate-landing"),
    path("painel/", AffiliateDashboardView.as_view(), name="affiliate-dashboard"),
    path("pix-key/", PixKeyUpdateView.as_view(), name="affiliate-pix-key"),
    path("saque/", PayoutRequestView.as_view(), name="affiliate-payout"),
]
