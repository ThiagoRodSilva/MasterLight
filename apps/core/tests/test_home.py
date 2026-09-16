"""Testes da página inicial (stats reais + destaques)."""

import re

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.core.models import SiteSettings
from apps.portfolio.models import PortfolioItem
from apps.tests.helpers import create_order, make_user


def _stat_value(content, label):
    m = re.search(re.escape(label) + r"</p>\s*<h3[^>]*>(\d+)</h3>", content)
    return int(m.group(1)) if m else None


class TestHomePage(TestCase):
    def setUp(self):
        self.provider = make_user(role=CustomUser.Role.PRESTADOR)

    def test_home_renders_stats(self):
        response = self.client.get(reverse("home"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Prestadores ativos" in content
        assert "Pedidos concluídos" in content

    def test_home_stats_reflect_db(self):
        client = make_user(role=CustomUser.Role.CLIENTE)
        order = create_order(client)
        order.status = "paid"
        order.save(update_fields=["status", "updated_at"])

        response = self.client.get(reverse("home"))
        content = response.content.decode()
        assert _stat_value(content, "Prestadores ativos") == 1
        assert _stat_value(content, "Pedidos concluídos") == 1

    def test_home_lists_recent_portfolio(self):
        PortfolioItem.objects.create(
            title="Projeto Residencial",
            created_by=self.provider,
            published=True,
        )
        response = self.client.get(reverse("home"))
        assert b"Projeto Residencial" in response.content

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

    def test_home_hides_provider_stat_when_services_disabled(self):
        settings = SiteSettings.load()
        settings.services_enabled = False
        settings.save(update_fields=["services_enabled"])
        response = self.client.get(reverse("home"))
        content = response.content.decode()
        assert "Prestadores ativos" not in content
