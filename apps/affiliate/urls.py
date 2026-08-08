from django.urls import path

from .views import AffiliateDashboardView, AffiliateLandingView, request_payout

urlpatterns = [
    path("", AffiliateLandingView.as_view(), name="affiliate-landing"),
    path("painel/", AffiliateDashboardView.as_view(), name="affiliate-dashboard"),
    path("saque/", request_payout, name="affiliate-payout"),
]
