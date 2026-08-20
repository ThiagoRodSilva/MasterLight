"""Testes da página inicial (stats reais + destaques)."""

import re

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.core.models import SiteSettings
from apps.portfolio.models import PortfolioItem
from apps.tests.helpers import create_order, make_product, make_user


def _stat_value(content, label):
    m = re.search(r"<strong>(\d+)</strong>\s*<span>" + label + "</span>", content)
    return int(m.group(1)) if m else None


class TestHomePage(TestCase):
    def setUp(self):
        self.provider = make_user(role=CustomUser.Role.PRESTADOR)
        self.featured = make_product(name="Produto Destaque", featured=True)
        make_product(name="Produto Comum", featured=False)

    def test_home_renders_stats(self):
        response = self.client.get(reverse("home"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Produtos na loja" in content
        assert "Prestadores ativos" in content
        assert "Pedidos concluídos" in content

    def test_home_stats_reflect_db(self):
        client = make_user(role=CustomUser.Role.CLIENTE)
        prod = make_product(name="Pedido Pago")
        create_order(client, product=prod)
        order = create_order(client, product=prod)
        order.status = "paid"
        order.save(update_fields=["status", "updated_at"])

        response = self.client.get(reverse("home"))
        content = response.content.decode()
        assert _stat_value(content, "Produtos na loja") == 3
        assert _stat_value(content, "Prestadores ativos") == 1
        assert _stat_value(content, "Pedidos concluídos") == 1

    def test_home_lists_featured_products(self):
        response = self.client.get(reverse("home"))
        assert b"Produto Destaque" in response.content
        assert b"Produto Comum" not in response.content

    def test_home_lists_recent_portfolio(self):
        PortfolioItem.objects.create(
            title="Projeto Residencial",
            created_by=self.provider,
            published=True,
        )
        response = self.client.get(reverse("home"))
        assert b"Projeto Residencial" in response.content

    def test_home_hides_destaques_when_store_disabled(self):
        settings = SiteSettings.load()
        settings.store_enabled = False
        settings.save(update_fields=["store_enabled"])
        response = self.client.get(reverse("home"))
        assert response.status_code == 200
        assert b"Produtos em destaque" not in response.content
        assert b"Produto Destaque" not in response.content


    def test_navbar_cart_badge_shows_count(self):
        from apps.checkout.models import Cart

        client = make_user(role=CustomUser.Role.CLIENTE)
        self.client.force_login(client)
        session = self.client.session
        session[Cart.SESSION_KEY] = {
            str(self.featured.pk): {
                "qty": 2,
                "price": float(self.featured.price),
                "name": self.featured.name,
            }
        }
        session.save()

        response = self.client.get(reverse("home"))
        assert b'badge-brand rounded-pill ms-1">2</span>' in response.content

    def test_navbar_cart_badge_hidden_when_empty(self):
        client = make_user(role=CustomUser.Role.CLIENTE)
        self.client.force_login(client)
        response = self.client.get(reverse("home"))
        assert b"rounded-pill ms-1" not in response.content
    def test_home_hides_portfolio_when_services_disabled(self):
        PortfolioItem.objects.create(
            title="Projeto Residencial",
            created_by=self.provider,
            published=True,
        )
        settings = SiteSettings.load()
        settings.services_enabled = False
        settings.save(update_fields=["services_enabled"])
        response = self.client.get(reverse("home"))
        content = response.content.decode()
        assert "Portfólio de prestadores" not in content
        assert "Projeto Residencial" not in content
