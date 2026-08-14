"""Testes do system check de configuracao do provedor de pagamento."""

from django.test import SimpleTestCase, override_settings

from apps.payments.checks import asaas_api_key_check


class AsaasApiKeyCheckTests(SimpleTestCase):
    def test_asaas_sem_chave_dispara_erro(self):
        with override_settings(PAYMENT_PROVIDER="asaas", ASAAS_API_KEY=""):
            errors = asaas_api_key_check(None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "payments.E001")
        self.assertIn("ASAAS_API_KEY", errors[0].msg)

    def test_asaas_com_chave_nao_dispara(self):
        with override_settings(PAYMENT_PROVIDER="asaas", ASAAS_API_KEY="$aact_chave"):
            errors = asaas_api_key_check(None)
        self.assertEqual(errors, [])

    def test_manual_sem_chave_nao_dispara(self):
        with override_settings(PAYMENT_PROVIDER="manual", ASAAS_API_KEY=""):
            errors = asaas_api_key_check(None)
        self.assertEqual(errors, [])
