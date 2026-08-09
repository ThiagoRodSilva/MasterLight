"""Fixtures e factories globais (pytest-django)."""

import json

import factory
import factory.fuzzy
import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import CustomUser
from apps.affiliate.models import AffiliateProfile
from apps.checkout.models import Order, OrderItem
from apps.shop.models import Category, Product


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()
        django_get_or_create = ("email",)

    @classmethod
    def _after_postgeneration(cls, instance, create, results=None):
        # Persiste o hash gerado por PostGenerationMethodCall("set_password")
        # (o save padrao de pos-geracao sera removido numa versao futura).
        if create:
            instance.save()

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "senha#123")
    role = CustomUser.Role.CLIENTE


class AffiliateProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AffiliateProfile

    user = factory.SubFactory(UserFactory)
    code = factory.Sequence(lambda n: f"CODE{n}")


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Categoria {n}")
    slug = factory.Sequence(lambda n: f"categoria-{n}")


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    sku = factory.Sequence(lambda n: f"SKU{n}")
    name = factory.Sequence(lambda n: f"Produto {n}")
    slug = factory.Sequence(lambda n: f"produto-{n}")
    price = factory.fuzzy.FuzzyDecimal(10.00, 100.00, precision=2)
    stock = 10
    category = factory.SubFactory(CategoryFactory)


def create_order(user, product=None, with_referral=False, qty=2):
    """Cria Order + OrderItem + Transaction (ManualPayment) para um teste."""
    if product is None:
        product = ProductFactory(stock=10)
    order = Order.objects.create(user=user, status=Order.Status.AWAITING_PAYMENT)
    OrderItem.objects.create(
        order=order,
        product=product,
        name=product.name,
        qty=qty,
        unit_price=product.price,
    )
    order.recompute_total()
    if with_referral:
        from apps.affiliate.models import Referral

        affil, _ = AffiliateProfile.objects.get_or_create(
            user=UserFactory(role=CustomUser.Role.AFILIADO)
        )
        Referral.objects.create(
            affiliate=affil,
            referred=user,
            order=order,
            commission_rate=affil.commission_rate,
            commission_amount=order.total * affil.commission_rate,
        )
    from apps.payments.models import Transaction

    Transaction.objects.create(order=order, user=user, provider="manual", amount=order.total)
    return order


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def client_user(user, client):
    client.force_login(user)
    return client


@pytest.fixture
def affiliate_profile(db):
    user = UserFactory(role=CustomUser.Role.AFILIADO)
    profile, _ = AffiliateProfile.objects.get_or_create(user=user)
    return profile


# ---------------------------------------------------------------------------
# Mock do Asaas (compartilhado entre payments e services)


class FakeResponse:
    """Objeto 'response' minimalista (ok/json/text) devolvido pelo mock."""

    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self._data

    @property
    def text(self):
        return json.dumps(self._data)


class FakeAsaasApi:
    """Mock do `requests.request` usado no AsaasGateway.

    Simula criacao de cliente/cobranca, consulta de Pix e reembolso.
    """

    def __init__(self):
        self.calls = []
        self.customer_id = "cus_0001"
        self.payment_id = "pay_0001"
        self.renewal_payment_id = "pay_0002"
        self.subscription_id = "sub_0001"
        self.card_token = "tok_0001"
        self.fail_next = None
        self.empty_subscription_payments = False

    def __call__(self, method, url, headers, json, timeout):
        self.calls.append({"method": method, "url": url, "body": json})
        if self.fail_next:
            status, detail = self.fail_next
            self.fail_next = None
            return FakeResponse({"errors": [detail]}, status_code=status)
        if method == "POST" and url.endswith("/customers"):
            return FakeResponse({"id": self.customer_id})
        if method == "POST" and url.endswith("/payments"):
            if json and json.get("billingType") == "CREDIT_CARD":
                return FakeResponse({"id": self.payment_id, "status": "PENDING"})
            return FakeResponse({"id": self.payment_id, "status": "PENDING"})
        if method == "POST" and url.endswith("/gerarCobranca"):
            return FakeResponse({"id": self.payment_id, "status": "PENDING"})
        if method == "POST" and url.endswith("/subscriptions"):
            self.subscription_id = "sub_0001"
            return FakeResponse({"id": self.subscription_id})
        if method == "POST" and url.endswith("/creditCards/tokenizeCreditCard"):
            return FakeResponse({"creditCardToken": self.card_token, "creditCardBrand": "VISA"})
        if method == "GET" and "subscriptions/" in url and url.endswith("/payments"):
            data = [] if self.empty_subscription_payments else [
                {"id": self.payment_id, "status": "PENDING", "value": 79.9}
            ]
            return FakeResponse({"data": data})
        if method == "GET" and f"payments/{self.payment_id}/pixQrCode" in url:
            return FakeResponse(
                {"encodedImage": "base64png", "payload": "00020126580014BR.GOV.BCB.PIX"}
            )
        if method == "GET" and "/pixQrCode" in url:
            return FakeResponse({"errors": [{"description": "cobranca sem pix"}]}, status_code=404)
        if method == "POST" and "refund" in url:
            return FakeResponse({"id": self.payment_id, "status": "REFUNDED"})
        raise AssertionError(f"Chamada inesperada: {method} {url}")


@pytest.fixture
def asaas(monkeypatch):
    fake = FakeAsaasApi()
    monkeypatch.setattr("requests.request", fake)
    return fake


@pytest.fixture
def activation():
    from django.test import override_settings

    with override_settings(
        PAYMENT_PROVIDER="asaas",
        ASAAS_API_KEY="teste-key",
        ASAAS_SANDBOX=True,
        ASAAS_WEBHOOK_TOKEN="segredo",
    ):
        yield
