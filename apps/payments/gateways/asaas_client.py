"""Cliente HTTP da API v3 do Asaas: retry, idempotência e formatação."""

import time
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings


class AsaasApiClient:
    """Chama endpoints `/api/v3` do Asaas com retry por falha transitória.

    Conhece apenas transporte HTTP: base URL, headers, idempotência e retry.
    Toda regra de negócio (cobrança, webhook) vive no
    `AsaasGateway`.
    """

    base_url_sandbox = "https://sandbox.asaas.com/api/v3"
    base_url_prod = "https://api.asaas.com/api/v3"
    timeout = 15

    @property
    def api_base_url(self) -> str:
        return self.base_url_prod if not settings.ASAAS_SANDBOX else self.base_url_sandbox

    def _headers(self) -> dict:
        return {
            "access_token": settings.ASAAS_API_KEY,
            "Content-Type": "application/json",
        }

    def _api(
        self,
        method: str,
        path: str,
        payload=None,
        params=None,
        *,
        idempotency_key: str = "",
    ) -> dict:
        """Chama a API do Asaas com retry por falha transitória e idempotência.

        - Retenta até 2x em `ConnectionError`/`Timeout`/`5xx` (backoff curto).
        - POSTs idempotentes enviam `X-Idempotency-Key` para evitar duplicidade.
        - Levanta `ValueError` em qualquer erro de HTTP após as tentativas.
        """
        if not settings.ASAAS_API_KEY:
            raise ValueError(
                "ASAAS_API_KEY não configurada. Defina a chave no .env ou nas env "
                "vars do ambiente (ex.: Vercel). Se o valor começa com '$', o "
                "django-environ pode tê-lo tratado como referência a outra env "
                "var e lido vazio; use a chave crua '$aact_...'."
            )
        url = f"{self.api_base_url}/{path.lstrip('/')}"
        headers = self._headers()
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        last_error = ""
        for attempt in range(3):
            try:
                response = requests.request(
                    method, url, headers=headers, json=payload, params=params, timeout=self.timeout
                )
            except requests.exceptions.RequestException as exc:
                last_error = f"Falha de conexão com o Asaas: {exc}"
                if attempt < 2:
                    time.sleep(0.25 * (attempt + 1))
                    continue
                raise ValueError(last_error) from exc
            if response.status_code in (500, 502, 503, 504) and attempt < 2:
                last_error = f"Erro Asaas {response.status_code}"
                time.sleep(0.25 * (attempt + 1))
                continue
            if not response.ok:
                try:
                    detail = response.json()
                except (ValueError, TypeError):
                    detail = response.text[:200]
                raise ValueError(f"Erro Asaas {response.status_code}: {detail}")
            return response.json()
        raise ValueError(last_error or "Falha ao comunicar com o Asaas após várias tentativas.")

    def _sanitize_digits(self, value: str) -> str:
        """Remove máscara de CPF/CNPJ, mantendo apenas dígitos."""
        return "".join(ch for ch in (value or "") if ch.isdigit())

    def _money(self, value) -> str:
        """Formata valor como string decimal fixa (evita precisão de float).

        Aceita Decimal, float ou str (o Asaas devolve `value` como string na
        consulta de cobranças).
        """
        try:
            return f"{Decimal(str(value)):.2f}"
        except InvalidOperation as exc:
            raise ValueError(f"Valor monetário inválido: {value!r}") from exc

    def fetch_payment(self, external_id: str) -> dict:
        """Consulta a cobrança atual no Asaas (reconciliação)."""
        return self._api("GET", f"payments/{external_id}")
