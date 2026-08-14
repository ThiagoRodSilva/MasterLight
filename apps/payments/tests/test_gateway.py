"""Testes da fabrica de gateway (registry)."""

from django.test import TestCase, override_settings

from apps.checkout.models import Address
from apps.payments.services import AsaasGateway, ManualGateway, get_gateway, prepare_card_payload
from apps.tests.helpers import make_user


class TestGetGateway(TestCase):
    def test_default_returns_manual(self):
        assert isinstance(get_gateway(), ManualGateway)

    @override_settings(PAYMENT_PROVIDER="asaas")
    def test_asaas_provider_returns_asaas_gateway(self):
        assert isinstance(get_gateway(), AsaasGateway)

    @override_settings(DEBUG=True, PAYMENT_PROVIDER="gateway-desconhecido")
    def test_unknown_provider_falls_back_to_manual_in_dev(self):
        assert isinstance(get_gateway(), ManualGateway)

    @override_settings(DEBUG=False, PAYMENT_PROVIDER="gateway-desconhecido")
    def test_unknown_provider_raises_in_production(self):
        from django.core.exceptions import ImproperlyConfigured

        with self.assertRaisesRegex(ImproperlyConfigured, "gateway-desconhecido"):
            get_gateway()


class TestPrepareCardPayload(TestCase):
    def _user(self):
        return make_user()

    def _address(self, user):
        return Address.objects.create(
            user=user,
            street="Rua A",
            number="10",
            city="Cidade",
            state="SP",
            zip_code="01001000",
            country="BR",
        )

    def _post(self, **overrides):
        base = {
            "card_holder": "Fulano",
            "card_cpf": "123.456.789-01",
            "card_number": "4111111111111111",
            "card_expiry_month": "12",
            "card_expiry_year": "2035",
            "card_ccv": "123",
        }
        base.update(overrides)
        return base

    def test_returns_card_and_holder_with_sanitized_cpf(self):
        user = self._user()
        address = self._address(user)
        card, holder = prepare_card_payload(self._post(), user, address)
        assert holder["cpf_cnpj"] == "12345678901"
        assert holder["postal_code"] == "01001000"
        assert holder["address_number"] == "10"
        assert card["expiry_month"] == "12"

    def test_missing_cpf_raises(self):
        user = self._user()
        address = self._address(user)
        with self.assertRaisesRegex(ValueError, "CPF"):
            prepare_card_payload(self._post(card_cpf=""), user, address)

    def test_falls_back_to_user_cpf(self):
        user = self._user()
        user.cpf = "11122233344"
        user.save(update_fields=["cpf"])
        address = self._address(user)
        card, holder = prepare_card_payload(self._post(card_cpf=""), user, address)
        assert holder["cpf_cnpj"] == "11122233344"

    def test_missing_address_raises(self):
        user = self._user()
        with self.assertRaisesRegex(ValueError, "endere"):
            prepare_card_payload(self._post(), user, None)

    def test_expired_card_raises(self):
        user = self._user()
        address = self._address(user)
        with self.assertRaisesRegex(ValueError, "vencido"):
            prepare_card_payload(
                self._post(card_expiry_month="01", card_expiry_year="2020"), user, address
            )
