"""Helpers compartilhados para testes."""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.affiliate.models import AffiliateProfile
from apps.checkout.models import Order, OrderItem

User = get_user_model()


def make_user(
    *,
    role: str = "cliente",
    email: str | None = None,
    cpf: str = "12345678901",
    telefone: str = "11999999999",
    address: dict | None = None,
    is_active: bool = True,
    **kwargs,
):
    """Cria um usuário de teste com CPF/telefone/endereço válidos para Asaas."""
    if email is None:
        from apps.core.models import random_slug

        email = f"{role}-{cpf[:6]}-{random_slug(6)}@test.com"
    user = User.objects.create_user(
        username=email,
        email=email,
        password="testpass123",
        role=role,
        cpf=cpf,
        telefone=telefone,
        is_active=is_active,
        **kwargs,
    )
    if address:
        from apps.checkout.models import Address

        Address.objects.create(user=user, **address)
    return user


def make_service_category(name: str = "Teste", slug: str | None = None):
    from apps.core.models import random_slug
    from apps.services.models import ServiceCategory

    if slug is None:
        slug = f"teste-{random_slug(6)}"
    return ServiceCategory.objects.create(name=name, slug=slug)


def make_service(
    *,
    name: str = "Serviço Teste",
    slug: str | None = None,
    base_price: Decimal = Decimal("49.90"),
    category=None,
    is_active: bool = True,
):
    from apps.core.models import random_slug
    from apps.services.models import Service

    if category is None:
        category = make_service_category()
    params = {
        "name": name,
        "base_price": base_price,
        "category": category,
        "is_active": is_active,
    }
    if slug is not None:
        params["slug"] = slug
    else:
        params["slug"] = f"servico-{random_slug(6)}"
    return Service.objects.create(**params)


def make_affiliate(user=None, commission_rate: Decimal = Decimal("0.10")) -> AffiliateProfile:
    if user is None:
        user = make_user(role="afiliado")
    affil, _ = AffiliateProfile.objects.get_or_create(
        user=user, defaults={"commission_rate": commission_rate}
    )
    return affil


def create_order(user=None, with_referral: bool = False, service=None, qty=1) -> Order:
    """Cria Order mínima com 1 item (serviço) — útil para testes de pagamento."""
    if user is None:
        user = make_user()
    order = Order.objects.create(user=user, status=Order.Status.OPEN)
    if service is None:
        service = make_service()
    OrderItem.objects.create(
        order=order, service=service, name=service.name, qty=qty, unit_price=service.base_price
    )
    order.recompute_total()
    if with_referral:
        from apps.affiliate.services import create_referral

        affil = make_affiliate()
        create_referral(affil.code, user, order, affil.commission_rate)
    # Cria transação manual para testes que manipulam status diretamente
    from apps.payments.models import Transaction

    Transaction.objects.create(
        order=order,
        user=user,
        provider="manual",
        amount=order.total,
        status=Transaction.Status.PENDING,
    )
    return order


class FakeResponse:
    @property
    def ok(self):
        return self.status_code < 400

    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class FakeAsaasApi:
    """Mock da API v3 do Asaas para testes unitários."""

    customer_id = "cus_0001"
    payment_id = "pay_0001"
    payment_link_id = "link_0001"
    payment_link_url = "https://asaas.com/payment/link_0001"
    checkout_id = "chk_0001"
    card_token = "tok_0001"
    customer_status = "PENDING"
    pix_missing = False
    fail_customer_creation = False
    fail_next = None

    def __init__(self):
        self.calls: list[dict] = []

    @property
    def checkout_url(self) -> str:
        return f"https://asaas.com/checkout/{self.checkout_id}"

    def __call__(self, method, url, headers=None, json=None, params=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "json": json,
                "params": params,
                "body": json,
            }
        )
        # Handle fail_next for testing retry logic
        if self.fail_next is not None:
            status_code, response_data = self.fail_next
            self.fail_next = None
            return FakeResponse(response_data, status_code=status_code)
        # POST /customers
        if method == "POST" and url.endswith("/customers"):
            if self.fail_customer_creation:
                return FakeResponse(
                    {
                        "errors": [
                            {"code": "invalid_object", "description": "cpfCnpj is required"},
                            {"code": "invalid_object", "description": "postalCode is required"},
                            {"code": "invalid_object", "description": "addressNumber is required"},
                            {"code": "invalid_object", "description": "province is required"},
                            {"code": "invalid_object", "description": "phoneNumber is required"},
                        ]
                    },
                    status_code=400,
                )
            if json and json.get("externalReference"):
                return FakeResponse(
                    {"id": self.customer_id, "externalReference": json["externalReference"]}
                )
            return FakeResponse({"id": self.customer_id})
        # GET /customers?email=...
        if method == "GET" and url.endswith("/customers"):
            return FakeResponse({"data": []})
        # POST /payments
        if method == "POST" and url.endswith("/payments"):
            return FakeResponse({"id": self.payment_id, "status": "PENDING"})
        # POST /paymentLinks
        if method == "POST" and url.endswith("/paymentLinks"):
            return FakeResponse(
                {
                    "id": self.payment_link_id,
                    "url": self.payment_link_url,
                    "value": (json or {}).get("value"),
                    "billingType": (json or {}).get("billingType"),
                    "active": True,
                }
            )
        # GET /checkouts/{id}
        if method == "GET" and "/checkouts/" in url and not url.endswith("/checkouts"):
            return FakeResponse(
                {
                    "id": self.checkout_id,
                    "url": f"https://asaas.com/checkout/{self.checkout_id}",
                    "status": "PAID",
                    "externalReference": "test-ref",
                }
            )
        # POST /checkouts
        if method == "POST" and url.endswith("/checkouts"):
            return FakeResponse(
                {
                    "id": self.checkout_id,
                    "url": f"https://asaas.com/checkout/{self.checkout_id}",
                    "status": "PENDING",
                    "externalReference": (json or {}).get("externalReference"),
                }
            )
        # GET /payments/{id}
        if (
            method == "GET"
            and f"payments/{self.payment_id}" in url
            and not url.endswith("pixQrCode")
        ):
            return FakeResponse({"id": self.payment_id, "status": self.customer_status})
        # GET /payments?externalReference=...
        if method == "GET" and url.endswith("/payments"):
            return FakeResponse({"data": [{"id": self.payment_id, "status": self.customer_status}]})
        # POST /creditCards/tokenizeCreditCard
        if method == "POST" and url.endswith("/creditCards/tokenizeCreditCard"):
            return FakeResponse({"creditCardToken": self.card_token, "creditCardBrand": "VISA"})
        # GET /payments/{id}/pixQrCode
        if method == "GET" and f"payments/{self.payment_id}/pixQrCode" in url:
            if self.pix_missing:
                return FakeResponse(
                    {"errors": [{"description": "pix indisponivel"}]}, status_code=404
                )
            return FakeResponse(
                {"encodedImage": "base64png", "payload": "00020126580014BR.GOV.BCB.PIX"}
            )
        # GET /payments/{id}/pixQrCode (other ids)
        if method == "GET" and "/pixQrCode" in url:
            return FakeResponse({"errors": [{"description": "cobranca sem pix"}]}, status_code=404)
        # POST /payments/{id}/refund
        if method == "POST" and "refund" in url:
            return FakeResponse({"id": self.payment_id, "status": "REFUNDED"})
        raise AssertionError(f"Chamada inesperada: {method} {url}")


@contextmanager
def mock_asaas():
    """Context manager: instala o `FakeAsaasApi` em `requests.request`.

    Útil quando apenas alguns métodos da classe precisam do mock (ex.: checkout).
    Uso: `with mock_asaas() as fake: ...`
    """
    fake = FakeAsaasApi()
    patcher = mock.patch("requests.request", fake)
    patcher.start()
    try:
        yield fake
    finally:
        patcher.stop()


class AsaasMockMixin:
    """Instala o `FakeAsaasApi` em `requests.request` para o teste inteiro.

    Substitui as fixtures `asaas`/`monkeypatch` do pytest: `self.asaas` fica
    disponível na classe. Combine com `@override_settings(PAYMENT_PROVIDER="asaas", ...)`.
    """

    def setUp(self):
        super().setUp()
        self.asaas = FakeAsaasApi()
        self._patcher = mock.patch("requests.request", self.asaas)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        super().tearDown()


class AsaasMockTestCase(TestCase):
    """Base que já instala o mock + settings Asaas."""

    def setUp(self):
        super().setUp()
        self.asaas = FakeAsaasApi()
        self._patcher = mock.patch("requests.request", self.asaas)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        super().tearDown()
