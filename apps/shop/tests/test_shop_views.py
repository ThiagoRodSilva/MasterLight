"""Smoke tests das views da loja (sprint 4)."""

from django.test import TestCase
from django.urls import reverse

from apps.core.models import SiteSettings
from apps.tests.helpers import make_category, make_product


class TestProductList(TestCase):
    def test_list_public_200_and_template(self):
        response = self.client.get(reverse("shop-list"))
        assert response.status_code == 200
        assert "shop/list.html" in response.template_name

    def test_list_shows_active_products_only(self):
        make_product(name="Ativo A")
        make_product(name="Inativo B", is_active=False)
        response = self.client.get(reverse("shop-list"))
        assert b"Ativo A" in response.content
        assert b"Inativo B" not in response.content

    def test_list_empty_state(self):
        response = self.client.get(reverse("shop-list"))
        assert b"Nenhum produto encontrado" in response.content

    def test_category_filter(self):
        active = make_category(name="Camisetas", slug="camisetas")
        other = make_category(name="Calças", slug="calcas")
        make_product(category=active, name="Camiseta Braba")
        make_product(category=other, name="Calça Jeans")
        response = self.client.get(reverse("shop-category", args=["camisetas"]))
        assert b"Camiseta Braba" in response.content
        assert "Calça Jeans".encode() not in response.content

    def test_search_filters_by_name(self):
        make_product(name="Impressora 3D")
        make_product(name="Marcador Percmanente")
        response = self.client.get(reverse("shop-list"), {"q": "impressora"})
        assert b"Impressora" in response.content
        assert b"Marcador" not in response.content

    def test_list_404_when_store_disabled(self):
        settings = SiteSettings.load()
        settings.store_enabled = False
        settings.save(update_fields=["store_enabled"])
        response = self.client.get(reverse("shop-list"))
        assert response.status_code == 404


class TestProductDetail(TestCase):
    def test_detail_200_for_active_product(self):
        product = make_product()
        response = self.client.get(reverse("shop-detail", args=[product.slug]))
        assert response.status_code == 200
        assert product.name.encode() in response.content

    def test_detail_404_inactive_product(self):
        product = make_product(is_active=False)
        response = self.client.get(reverse("shop-detail", args=[product.slug]))
        assert response.status_code == 404
