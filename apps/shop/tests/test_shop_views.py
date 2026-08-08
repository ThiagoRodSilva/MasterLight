"""Smoke tests das views da loja (sprint 4)."""

import pytest
from django.urls import reverse

from apps.core.models import SiteSettings
from conftest import CategoryFactory, ProductFactory

pytestmark = pytest.mark.django_db


class TestProductList:
    def test_list_public_200_and_template(self, client):
        response = client.get(reverse("shop-list"))
        assert response.status_code == 200
        assert "shop/list.html" in response.template_name

    def test_list_shows_active_products_only(self, client):
        ProductFactory(name="Ativo A")
        ProductFactory(name="Inativo B", is_active=False)
        response = client.get(reverse("shop-list"))
        assert b"Ativo A" in response.content
        assert b"Inativo B" not in response.content

    def test_list_empty_state(self, client):
        response = client.get(reverse("shop-list"))
        assert b"Nenhum produto encontrado" in response.content

    def test_category_filter(self, client):
        active = CategoryFactory(name="Camisetas", slug="camisetas")
        other = CategoryFactory(name="Calças", slug="calcas")
        ProductFactory(category=active, name="Camiseta Braba")
        ProductFactory(category=other, name="Calça Jeans")
        response = client.get(reverse("shop-category", args=["camisetas"]))
        assert b"Camiseta Braba" in response.content
        assert "Calça Jeans".encode() not in response.content

    def test_search_filters_by_name(self, client):
        ProductFactory(name="Impressora 3D")
        ProductFactory(name="Marcador Percmanente")
        response = client.get(reverse("shop-list"), {"q": "impressora"})
        assert b"Impressora" in response.content
        assert b"Marcador" not in response.content

    def test_list_404_when_store_disabled(self, client):
        settings = SiteSettings.load()
        settings.store_enabled = False
        settings.save(update_fields=["store_enabled"])
        response = client.get(reverse("shop-list"))
        assert response.status_code == 404


class TestProductDetail:
    def test_detail_200_for_active_product(self, client):
        product = ProductFactory()
        response = client.get(reverse("shop-detail", args=[product.slug]))
        assert response.status_code == 200
        assert product.name.encode() in response.content

    def test_detail_404_inactive_product(self, client):
        product = ProductFactory(is_active=False)
        response = client.get(reverse("shop-detail", args=[product.slug]))
        assert response.status_code == 404
