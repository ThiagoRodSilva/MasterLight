"""Testes do portfolio (visibilidade)."""
import pytest
from django.shortcuts import reverse

from apps.portfolio.models import PortfolioItem
from conftest import UserFactory

pytestmark = pytest.mark.django_db


class TestPortfolioVisibility:
    def test_unpublished_item_404_on_detail(self, client):
        owner = UserFactory()
        item = PortfolioItem.objects.create(
            title="Privado", description="", category="", published=False, created_by=owner
        )
        response = client.get(reverse("portfolio-detail", args=[item.pk]))
        assert response.status_code == 404

    def test_published_item_200_on_detail(self, client):
        owner = UserFactory()
        item = PortfolioItem.objects.create(
            title="Publico", description="", category="", published=True, created_by=owner
        )
        response = client.get(reverse("portfolio-detail", args=[item.pk]))
        assert response.status_code == 200

    def test_inactive_item_404_on_detail(self, client):
        owner = UserFactory()
        item = PortfolioItem.objects.create(
            title="Inativo", description="", category="", published=True,
            is_active=False, created_by=owner,
        )
        response = client.get(reverse("portfolio-detail", args=[item.pk]))
        assert response.status_code == 404
