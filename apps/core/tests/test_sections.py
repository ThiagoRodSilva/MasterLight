"""Testes de desabilitação de seções via SiteSettings."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.core.models import SiteSettings
from apps.services.models import Service, ServiceCategory
from apps.tests.helpers import make_product, make_user


def _unset(flag):
    obj = SiteSettings.load()
    setattr(obj, flag, False)
    obj.save(update_fields=[flag])


class TestStoreDisabled(TestCase):
    def _login(self):
        user = make_user(is_superuser=True)
        self.client.force_login(user)
        return user

    def test_product_list_404(self):
        _unset("store_enabled")
        response = self.client.get(reverse("shop-list"))
        assert response.status_code == 404

    def test_product_detail_404(self):
        product = make_product(slug="produto-teste")
        _unset("store_enabled")
        response = self.client.get(reverse("shop-detail", kwargs={"slug": product.slug}))
        assert response.status_code == 404

    def test_home_hides_loja_links(self):
        _unset("store_enabled")
        response = self.client.get("/")
        assert response.status_code == 200
        assert b"Ver produtos" not in response.content
        assert b"Ver loja" not in response.content

    def test_navbar_hides_loja_link(self):
        _unset("store_enabled")
        response = self.client.get("/")
        assert b"/loja/" not in response.content

    def test_cart_add_blocked(self):
        product = make_product(slug="produto-teste")
        self._login()
        _unset("store_enabled")
        response = self.client.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "1"})
        assert response.status_code == 302
        assert response.url == reverse("home")

    def test_checkout_blocked(self):
        self._login()
        _unset("store_enabled")
        response = self.client.get(reverse("checkout"))
        assert response.status_code == 302
        assert response.url == reverse("home")


class TestServicesDisabled(TestCase):
    def test_services_list_404(self):
        _unset("services_enabled")
        response = self.client.get(reverse("services-list"))
        assert response.status_code == 404

    def test_services_detail_404(self):
        category = ServiceCategory.objects.create(name="Cat", slug="cat")
        Service.objects.create(name="Servico Teste", slug="servico-teste", category=category)
        _unset("services_enabled")
        response = self.client.get(reverse("services-detail", kwargs={"slug": "servico-teste"}))
        assert response.status_code == 404

    def test_home_hides_pedir_servico(self):
        _unset("services_enabled")
        response = self.client.get("/")
        assert b"Pedir um servi" not in response.content


class TestAffiliateDisabled(TestCase):
    def test_landing_404(self):
        _unset("affiliates_enabled")
        response = self.client.get(reverse("affiliate-landing"))
        assert response.status_code == 404

    def test_dashboard_404(self):
        from apps.affiliate.models import AffiliateProfile

        user = make_user(role=CustomUser.Role.AFILIADO, is_superuser=True)
        AffiliateProfile.objects.get_or_create(user=user)
        _unset("affiliates_enabled")
        self.client.force_login(user)
        response = self.client.get(reverse("affiliate-dashboard"))
        assert response.status_code == 404

    def test_home_hides_afiliado_link(self):
        _unset("affiliates_enabled")
        response = self.client.get("/")
        assert b"Seja um afiliado" not in response.content


class TestAllEnabledDefault(TestCase):
    def test_sections_available_by_default(self):
        product = make_product(slug="produto-teste")
        assert self.client.get(reverse("shop-list")).status_code == 200
        assert (
            self.client.get(reverse("shop-detail", kwargs={"slug": product.slug})).status_code
            == 200
        )
        assert self.client.get(reverse("services-list")).status_code == 200
        assert self.client.get(reverse("affiliate-landing")).status_code == 200
