"""Testes da fabrica de gateway (registry)."""

from django.test import override_settings

from apps.payments.services import AsaasGateway, ManualGateway, get_gateway


class TestGetGateway:
    def test_default_returns_manual(self):
        assert isinstance(get_gateway(), ManualGateway)

    @override_settings(PAYMENT_PROVIDER="asaas")
    def test_asaas_provider_returns_asaas_gateway(self):
        assert isinstance(get_gateway(), AsaasGateway)

    @override_settings(PAYMENT_PROVIDER="gateway-desconhecido")
    def test_unknown_provider_falls_back_to_manual(self):
        assert isinstance(get_gateway(), ManualGateway)
