"""Testes de desabilitação de seções via SiteSettings."""
import pytest
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.core.models import SiteSettings
from apps.services.models import Service, ServiceCategory
from conftest import ProductFactory, UserFactory

pytestmark = pytest.mark.django_db


def _unset(flag):
    obj = SiteSettings.load()
    setattr(obj, flag, False)
    obj.save(update_fields=[flag])


class TestStoreDisabled:
    def test_product_list_404(self, client):
        _unset("store_enabled")
        response = client.get(reverse("shop-list"))
        assert response.status_code == 404

    def test_product_detail_404(self, client):
        product = ProductFactory(slug="produto-teste")
        _unset("store_enabled")
        response = client.get(reverse("shop-detail", kwargs={"slug": product.slug}))
        assert response.status_code == 404

    def test_home_hides_loja_links(self, client):
        _unset("store_enabled")
        response = client.get("/")
        assert response.status_code == 200
        assert b"Ver produtos" not in response.content
        assert b"Ver loja" not in response.content

    def test_navbar_hides_loja_link(self, client):
        _unset("store_enabled")
        response = client.get("/")
        assert b"/loja/" not in response.content

    def test_cart_add_blocked(self, client_user):
        product = ProductFactory(slug="produto-teste")
        _unset("store_enabled")
        response = client_user.post(
            reverse("checkout-cart-add", args=[product.pk]), {"qty": "1"}
        )
        assert response.status_code == 302
        assert response.url == reverse("home")

    def test_checkout_blocked(self, client_user):
        _unset("store_enabled")
        response = client_user.get(reverse("checkout"))
        assert response.status_code == 302
        assert response.url == reverse("home")


class TestServicesDisabled:
    def test_services_list_404(self, client):
        _unset("services_enabled")
        response = client.get(reverse("services-list"))
        assert response.status_code == 404

    def test_services_detail_404(self, client):
        category = ServiceCategory.objects.create(name="Cat", slug="cat")
        Service.objects.create(
            name="Servico Teste", slug="servico-teste", category=category
        )
        _unset("services_enabled")
        response = client.get(
            reverse("services-detail", kwargs={"slug": "servico-teste"})
        )
        assert response.status_code == 404

    def test_home_hides_pedir_servico(self, client):
        _unset("services_enabled")
        response = client.get("/")
        assert b"Pedir um servi" not in response.content


class TestAffiliateDisabled:
    def test_landing_404(self, client):
        _unset("affiliates_enabled")
        response = client.get(reverse("affiliate-landing"))
        assert response.status_code == 404

    def test_dashboard_404(self, client):
        user = UserFactory(role=CustomUser.Role.AFILIADO)
        from apps.affiliate.models import AffiliateProfile

        AffiliateProfile.objects.get_or_create(user=user)
        _unset("affiliates_enabled")
        client.force_login(user)
        response = client.get(reverse("affiliate-dashboard"))
        assert response.status_code == 404

    def test_home_hides_afiliado_link(self, client):
        _unset("affiliates_enabled")
        response = client.get("/")
        assert b"Seja um afiliado" not in response.content


class TestAllEnabledDefault:
    def test_sections_available_by_default(self, client):
        product = ProductFactory(slug="produto-teste")
        assert client.get(reverse("shop-list")).status_code == 200
        assert (
            client.get(reverse("shop-detail", kwargs={"slug": product.slug})).status_code
            == 200
        )
        assert client.get(reverse("services-list")).status_code == 200
        assert client.get(reverse("affiliate-landing")).status_code == 200
