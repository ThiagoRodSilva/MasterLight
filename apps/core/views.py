"""Views globais (home)."""

from django.db.models import Q
from django.shortcuts import render

from apps.accounts.models import CustomUser
from apps.checkout.models import Order
from apps.core.models import SiteSettings
from apps.portfolio.models import PortfolioItem


def home_view(request):
    settings = SiteSettings.load()

    portfolio = []
    if settings.services_enabled:
        portfolio = list(
            PortfolioItem.objects.filter(is_active=True, published=True).select_related(
                "created_by"
            )[:3]
        )

    paid_orders = Order.objects.filter(
        Q(status=Order.Status.PAID) | Q(status=Order.Status.COMPLETED)
    ).count()

    stats = []
    if settings.services_enabled:
        stats.append(
            {
                "value": CustomUser.objects.filter(
                    role=CustomUser.Role.PRESTADOR, is_active=True
                ).count(),
                "label": "Prestadores ativos",
            }
        )
    stats.append(
        {
            "value": paid_orders,
            "label": "Pedidos concluídos",
        }
    )

    return render(
        request,
        "home.html",
        {
            "portfolio": portfolio,
            "stats": stats,
        },
    )
