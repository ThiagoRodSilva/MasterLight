"""Testes do app checkout (endereço de entrega/cobrança)."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.checkout.models import Address
from apps.tests.helpers import make_user


def _address_data(**overrides):
    data = {
        "street": "Rua Teste",
        "number": "123",
        "city": "São Paulo",
        "state": "SP",
        "zip_code": "01001-000",
        "country": "Brasil",
    }
    data.update(overrides)
    return data


class TestAddressCreateView(TestCase):
    def test_creates_address_and_redirects(self):
        user = make_user(role=CustomUser.Role.CLIENTE)
        self.client.force_login(user)
        response = self.client.post(reverse("checkout-address"), _address_data())
        assert response.status_code == 302
        assert response.url == reverse("accounts-me")
        address = Address.objects.filter(user=user).first()
        assert address is not None
        assert address.street == "Rua Teste"

    def test_requires_login(self):
        response = self.client.get(reverse("checkout-address"))
        assert response.status_code in (302, 403)
        assert Address.objects.count() == 0

    def test_restricted_to_cliente_role(self):
        for role in (CustomUser.Role.PRESTADOR, CustomUser.Role.AFILIADO):
            with self.subTest(role=role):
                user = make_user(role=role)
                self.client.force_login(user)
                response = self.client.get(reverse("checkout-address"))
                assert response.status_code in (302, 403)

    def test_admin_can_access(self):
        admin = make_user(role=CustomUser.Role.ADMIN, is_superuser=True)
        self.client.force_login(admin)
        response = self.client.get(reverse("checkout-address"))
        assert response.status_code == 200

    def test_invalid_form_shows_errors(self):
        user = make_user(role=CustomUser.Role.CLIENTE)
        self.client.force_login(user)
        response = self.client.post(reverse("checkout-address"), _address_data(street=""))
        assert response.status_code == 200
        assert b"error" in response.content.lower() or b"field-error" in response.content.lower()
        assert Address.objects.count() == 0
