"""Testes do portfolio (visibilidade)."""

from django.shortcuts import reverse
from django.test import TestCase

from apps.portfolio.models import PortfolioItem
from apps.tests.helpers import make_user


class TestPortfolioVisibility(TestCase):
    def test_unpublished_item_404_on_detail(self):
        owner = make_user()
        item = PortfolioItem.objects.create(
            title="Privado", description="", category="", published=False, created_by=owner
        )
        response = self.client.get(reverse("portfolio-detail", args=[item.pk]))
        assert response.status_code == 404

    def test_published_item_200_on_detail(self):
        owner = make_user()
        item = PortfolioItem.objects.create(
            title="Publico", description="", category="", published=True, created_by=owner
        )
        response = self.client.get(reverse("portfolio-detail", args=[item.pk]))
        assert response.status_code == 200

    def test_inactive_item_404_on_detail(self):
        owner = make_user()
        item = PortfolioItem.objects.create(
            title="Inativo",
            description="",
            category="",
            published=True,
            is_active=False,
            created_by=owner,
        )
        response = self.client.get(reverse("portfolio-detail", args=[item.pk]))
        assert response.status_code == 404
