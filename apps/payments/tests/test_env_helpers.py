"""Testes da leitura da chave do Asaas (env_helpers.py).

Cobre o bug de producao/Vercel: o django-environ trata valores que comecam
com '$' como referencia a outra env var e os zerava, quebrando a integracao
com "ASAAS_API_KEY não configurada".
"""

import os
from unittest import mock

from django.test import SimpleTestCase

from config.settings.env_helpers import asaas_api_key


class AsaasApiKeyTests(SimpleTestCase):
    CRUA = "$aact_hmlg_000MzkwODA2MWY2OGM3MWRlMDU2NWM3MzJlNzZmNGZhZGY"
    ESCAPADA = r"\$aact_hmlg_000MzkwODA2MWY2OGM3MWRlMDU2NWM3MzJlNzZmNGZhZGY"

    def test_chave_crua_e_mantida(self):
        with mock.patch.dict(os.environ, {"ASAAS_API_KEY": self.CRUA}, clear=False):
            self.assertEqual(asaas_api_key(), self.CRUA)

    def test_chave_escapada_legada_e_desescapada(self):
        with mock.patch.dict(os.environ, {"ASAAS_API_KEY": self.ESCAPADA}, clear=False):
            self.assertEqual(asaas_api_key(), self.CRUA)

    def test_cifrao_no_meio_nao_e_interpretado_como_proxy(self):
        valor = self.CRUA + "OTo6JGFhY2hfNGI2"
        with mock.patch.dict(os.environ, {"ASAAS_API_KEY": valor}, clear=False):
            self.assertEqual(asaas_api_key(), valor)

    def test_ausente_retorna_vazio(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ASAAS_API_KEY", None)
            self.assertEqual(asaas_api_key(), "")
