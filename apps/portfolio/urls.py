from django.urls import path

from .views import (
    PortfolioCreateView,
    PortfolioDetailView,
    PortfolioListView,
    PortfolioUpdateView,
)

urlpatterns = [
    path("", PortfolioListView.as_view(), name="portfolio-list"),
    path("novo/", PortfolioCreateView.as_view(), name="portfolio-create"),
    path("<uuid:pk>/", PortfolioDetailView.as_view(), name="portfolio-detail"),
    path("<uuid:pk>/editar/", PortfolioUpdateView.as_view(), name="portfolio-update"),
]
