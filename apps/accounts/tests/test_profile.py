"""Testes do perfil: dados de pagamento no cadastro e edição de dados."""

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.forms import CustomSignupForm
from apps.accounts.models import CustomUser
from apps.checkout.models import Address
from apps.core.validators import validate_brazilian_cpf
from apps.tests.helpers import make_user

SIGNUP_ADDRESS = {
    "street": "Rua das Flores",
    "number": "42",
    "city": "São Paulo",
    "state": "SP",
    "zip_code": "01310-100",
    "country": "Brasil",
}

SIGNUP_DATA = {
    "role": CustomUser.Role.CLIENTE,
    "cpf": "111.444.777-35",
    "telefone": "(11) 99999-0000",
}


class TestCpfValidator(TestCase):
    def test_valid_masked_cpf(self):
        validate_brazilian_cpf("111.444.777-35")

    def test_valid_plain_cpf(self):
        validate_brazilian_cpf("11144477735")

    def test_repeated_digits_invalid(self):
        with self.assertRaises(ValidationError):
            validate_brazilian_cpf("111.111.111-11")

    def test_bad_checksum_invalid(self):
        with self.assertRaises(ValidationError):
            validate_brazilian_cpf("111.444.777-00")


class TestCustomSignupFormRequiredData(TestCase):
    def test_requires_cpf_telefone_and_address_for_all_roles(self):
        form = CustomSignupForm(data={"role": CustomUser.Role.CLIENTE})
        assert not form.is_valid()
        for field in ("cpf", "telefone", "street", "number", "city", "state", "zip_code"):
            assert field in form.errors, field

    def test_rejects_invalid_cpf(self):
        form = CustomSignupForm(data={**SIGNUP_DATA, **SIGNUP_ADDRESS, "cpf": "111.111.111-11"})
        assert not form.is_valid()
        assert "cpf" in form.errors

    def test_signup_sanitizes_and_creates_address(self):
        form = CustomSignupForm(data={**SIGNUP_DATA, **SIGNUP_ADDRESS})
        assert form.is_valid(), form.errors
        user = CustomUser(email="cli@example.com", username="cli")
        user.save()
        form.signup(None, user)
        user.refresh_from_db()
        assert user.cpf == "11144477735"
        assert user.telefone == "11999990000"
        address = Address.objects.get(user=user)
        assert address.zip_code == "01310100"
        assert address.street == "Rua das Flores"


class TestProfileEditView(TestCase):
    def _post(self, user, **overrides):
        data = {
            **SIGNUP_ADDRESS,
            "cpf": "111.444.777-35",
            "telefone": "(11) 99999-0000",
            "email": user.email,
            **overrides,
        }
        return self.client.post(reverse("accounts-me-edit"), data)

    def test_requires_login(self):
        response = self.client.get(reverse("accounts-me-edit"))
        assert response.status_code in (301, 302)
        assert "/login/" in response.url

    def test_edit_creates_address(self):
        user = make_user(role=CustomUser.Role.CLIENTE)
        self.client.force_login(user)
        response = self._post(user, first_name="Ana", last_name="Silva")
        assert response.status_code == 302
        user.refresh_from_db()
        assert user.cpf == "11144477735"
        assert user.telefone == "11999990000"
        assert user.first_name == "Ana"
        address = Address.objects.get(user=user)
        assert address.zip_code == "01310100"

    def test_edit_updates_existing_address(self):
        user = make_user(role=CustomUser.Role.CLIENTE)
        address = Address.objects.create(
            user=user,
            street="Rua Velha",
            number="1",
            city="Campinas",
            state="SP",
            zip_code="13000000",
        )
        self.client.force_login(user)
        response = self._post(user)
        assert response.status_code == 302
        address.refresh_from_db()
        assert address.street == "Rua das Flores"
        assert Address.objects.filter(user=user).count() == 1

    def test_edit_rejects_invalid_cpf(self):
        user = make_user(role=CustomUser.Role.CLIENTE)
        self.client.force_login(user)
        response = self._post(user, cpf="111.111.111-11")
        assert response.status_code == 200
        assert "CPF" in response.content.decode()

    def test_form_prefilled(self):
        user = make_user(role=CustomUser.Role.CLIENTE, cpf="11144477735", telefone="11999990000")
        Address.objects.create(user=user, **SIGNUP_ADDRESS)
        self.client.force_login(user)
        response = self.client.get(reverse("accounts-me-edit"))
        form = response.context["form"]
        assert form["cpf"].value() == "11144477735"
        assert form["street"].value() == "Rua das Flores"
