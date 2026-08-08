from django.urls import path

from .views import AffiliateDashboardView, AffiliateLandingView, PayoutRequestView

urlpatterns = [
    path("", AffiliateLandingView.as_view(), name="affiliate-landing"),
    path("painel/", AffiliateDashboardView.as_view(), name="affiliate-dashboard"),
    path("saque/", PayoutRequestView.as_view(), name="affiliate-payout"),
]
