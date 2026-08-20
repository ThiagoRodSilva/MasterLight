"""Views globais (home)."""

from django.db.models import Q
from django.shortcuts import render

from apps.accounts.models import CustomUser
from apps.checkout.models import Order
from apps.core.models import SiteSettings
from apps.portfolio.models import PortfolioItem
from apps.shop.models import Product


def home_view(request):
    settings = SiteSettings.load()

    products = []
    portfolio = []
    if settings.store_enabled:
        products = list(
            Product.objects.filter(is_active=True, featured=True)
            .select_related("category")
            .prefetch_related("images")[:6]
        )
    if settings.services_enabled:
        portfolio = list(
            PortfolioItem.objects.filter(is_active=True, published=True)
            .select_related("created_by")[:3]
        )

    paid_orders = Order.objects.filter(
        Q(status=Order.Status.PAID) | Q(status=Order.Status.COMPLETED)
    ).count()

    stats = []
    if settings.store_enabled:
        stats.append(
            {
                "value": Product.objects.filter(is_active=True).count(),
                "label": "Produtos na loja",
            }
        )
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
            "products": products,
            "portfolio": portfolio,
            "stats": stats,
        },
    )
