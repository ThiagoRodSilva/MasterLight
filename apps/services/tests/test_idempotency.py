"""Testes de idempotencia e validacoes extras para Services."""

from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.checkout.models import Order
from apps.core.models import SiteSettings
from apps.services.models import Service, ServiceCategory, ServiceRequest
from apps.tests.helpers import AsaasMockMixin, make_user


class TestIdempotency(AsaasMockMixin, TestCase):
    """Testes de idempotencia: POST duplicado nao deve criar duplicatas."""

    def setUp(self):
        super().setUp()
        self.category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica")
        self.provider = make_user(role=CustomUser.Role.PRESTADOR)
        self.cliente = make_user(role=CustomUser.Role.CLIENTE)
        self.service = Service.objects.create(
            name="Instalação",
            slug="instalacao",
            base_price=10,
            category=self.category,
            created_by=self.provider,
        )
        self.service.providers.add(self.provider)

    def _make_quoted_request(self):
        return ServiceRequest.objects.create(
            cliente=self.cliente,
            service=self.service,
            prestador=self.provider,
            status=ServiceRequest.Status.QUOTED,
            final_price=Decimal("99.90"),
        )

    def test_double_post_approve_creates_single_order(self):
        """Duplo POST em services-request-approve deve criar apenas 1 Order."""
        sr = self._make_quoted_request()
        self.client.force_login(self.cliente)

        # Primeiro POST
        response1 = self.client.post(reverse("services-request-approve", kwargs={"pk": sr.pk}))
        assert response1.status_code == 302
        sr.refresh_from_db()
        order1 = sr.order
        assert order1 is not None
        assert Order.objects.filter(user=self.cliente).count() == 1

        # Segundo POST (duplo submit)
        response2 = self.client.post(reverse("services-request-approve", kwargs={"pk": sr.pk}))
        assert response2.status_code == 302
        sr.refresh_from_db()
        # Deve redirecionar com mensagem de erro, nao criar 2a order
        assert Order.objects.filter(user=self.cliente).count() == 1
        assert sr.order == order1  # Mesma order


class TestQuoteFormValidation(TestCase):
    """Testes de validacao do QuoteForm."""

    def setUp(self):
        super().setUp()
        self.category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica")
        self.provider = make_user(role=CustomUser.Role.PRESTADOR)
        self.service = Service.objects.create(
            name="Instalação",
            slug="instalacao",
            base_price=Decimal("50.00"),
            category=self.category,
            created_by=self.provider,
        )
        self.service.providers.add(self.provider)

    def test_quote_form_rejects_negative_price(self):
        """QuoteForm deve rejeitar final_price negativo."""
        from apps.services.forms import QuoteForm

        sr = ServiceRequest.objects.create(
            cliente=make_user(role=CustomUser.Role.CLIENTE),
            service=self.service,
            prestador=self.provider,
            status=ServiceRequest.Status.PENDING,
        )
        form = QuoteForm(data={"final_price": "-10.00"}, instance=sr)
        assert not form.is_valid()
        assert "final_price" in form.errors
        sr.refresh_from_db()
        assert sr.status == ServiceRequest.Status.PENDING  # Status nao muda

    def test_quote_form_accepts_zero_price(self):
        """QuoteForm deve aceitar final_price = 0 (orcamento gratis)."""
        from apps.services.forms import QuoteForm

        sr = ServiceRequest.objects.create(
            cliente=make_user(role=CustomUser.Role.CLIENTE),
            service=self.service,
            prestador=self.provider,
            status=ServiceRequest.Status.PENDING,
        )
        form = QuoteForm(data={"final_price": "0.00"}, instance=sr)
        assert form.is_valid()
        # Form valido - a view define status=QUOTED e preenche base_price se vazio
        form.save()
        sr.refresh_from_db()
        assert sr.final_price == Decimal("0.00")

    def test_quote_form_blank_uses_base_price(self):
        """QuoteForm com final_price vazio deve ser valido (view preenche com base_price)."""
        from apps.services.forms import QuoteForm

        sr = ServiceRequest.objects.create(
            cliente=make_user(role=CustomUser.Role.CLIENTE),
            service=self.service,
            prestador=self.provider,
            status=ServiceRequest.Status.PENDING,
        )
        form = QuoteForm(data={"final_price": ""}, instance=sr)
        assert form.is_valid()
        # Form valido com campo vazio - a view preenche com base_price no form_valid
        form.save()
        sr.refresh_from_db()
        # O form salva None, a view depois preenche com base_price
        assert sr.final_price is None or sr.final_price == self.service.base_price


class TestFinalPriceZero(AsaasMockMixin, TestCase):
    """Testes para final_price = 0 na aprovacao."""

    def setUp(self):
        super().setUp()
        self.category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica")
        self.provider = make_user(role=CustomUser.Role.PRESTADOR)
        self.cliente = make_user(role=CustomUser.Role.CLIENTE)
        self.service = Service.objects.create(
            name="Instalação",
            slug="instalacao",
            base_price=Decimal("50.00"),
            category=self.category,
            created_by=self.provider,
        )
        self.service.providers.add(self.provider)

    def test_approve_with_final_price_zero_creates_order_item_zero(self):
        """Aprovar orçamento com final_price=0 deve criar OrderItem com unit_price=0."""
        sr = ServiceRequest.objects.create(
            cliente=self.cliente,
            service=self.service,
            prestador=self.provider,
            status=ServiceRequest.Status.QUOTED,
            final_price=Decimal("0.00"),
        )
        self.client.force_login(self.cliente)
        response = self.client.post(reverse("services-request-approve", kwargs={"pk": sr.pk}))
        assert response.status_code == 302
        sr.refresh_from_db()
        order = sr.order
        assert order is not None
        from apps.checkout.models import OrderItem

        item = OrderItem.objects.get(order=order)
        assert item.unit_price == Decimal("0.00")
        assert order.total == Decimal("0.00")


class TestCancelRequestCancelsOrder(AsaasMockMixin, TestCase):
    """Cancelar request com Order AWAITING_PAYMENT deve cancelar a Order."""

    def setUp(self):
        super().setUp()
        self.category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica")
        self.provider = make_user(role=CustomUser.Role.PRESTADOR)
        self.cliente = make_user(role=CustomUser.Role.CLIENTE)
        self.service = Service.objects.create(
            name="Instalação",
            slug="instalacao",
            base_price=Decimal("50.00"),
            category=self.category,
            created_by=self.provider,
        )
        self.service.providers.add(self.provider)

    def test_cancel_request_cancels_awaiting_payment_order(self):
        """Cancelar request com Order AWAITING_PAYMENT deve setar Order.status = CANCELED."""
        sr = ServiceRequest.objects.create(
            cliente=self.cliente,
            service=self.service,
            prestador=self.provider,
            status=ServiceRequest.Status.QUOTED,
            final_price=Decimal("99.90"),
        )
        # Aprovar para criar order
        self.client.force_login(self.cliente)
        self.client.post(reverse("services-request-approve", kwargs={"pk": sr.pk}))
        sr.refresh_from_db()
        order = sr.order
        assert order.status == Order.Status.AWAITING_PAYMENT

        # Cancelar request
        response = self.client.post(reverse("services-request-cancel", kwargs={"pk": sr.pk}))
        assert response.status_code == 302
        sr.refresh_from_db()
        order.refresh_from_db()
        assert sr.status == ServiceRequest.Status.CANCELED
        assert order.status == Order.Status.CANCELED


class TestGetMethodReturns405(TestCase):
    """GET em views POST-only nao deve levantar 500."""

    def setUp(self):
        super().setUp()
        self.category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica")
        self.provider = make_user(role=CustomUser.Role.PRESTADOR)
        self.cliente = make_user(role=CustomUser.Role.CLIENTE)
        self.service = Service.objects.create(
            name="Instalação",
            slug="instalacao",
            base_price=Decimal("50.00"),
            category=self.category,
            created_by=self.provider,
        )
        self.service.providers.add(self.provider)

    def test_get_request_cancel_returns_405_or_redirect(self):
        """GET em services-request-cancel deve retornar 405 ou redirect (nao 500)."""
        sr = ServiceRequest.objects.create(
            cliente=self.cliente,
            service=self.service,
            prestador=self.provider,
            status=ServiceRequest.Status.QUOTED,
        )
        self.client.force_login(self.cliente)
        response = self.client.get(reverse("services-request-cancel", kwargs={"pk": sr.pk}))
        # View foi convertida para View POST-only com get() redirecionando
        assert response.status_code in (302, 405)


class TestServiceListViewMineExcludesInactive(TestCase):
    """ServiceListViewMine nao deve listar servicos com is_active=False."""

    def test_inactive_service_not_listed(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica-inactive")
        Service.objects.create(
            name="Ativo",
            slug="ativo",
            base_price=10,
            category=category,
            created_by=provider,
            is_active=True,
        )
        Service.objects.create(
            name="Inativo",
            slug="inativo",
            base_price=10,
            category=category,
            created_by=provider,
            is_active=False,
        )
        self.client.force_login(provider)
        response = self.client.get(reverse("services-my"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Ativo" in content
        assert "Inativo" not in content


@override_settings(SERVICES_ENABLED=True)
class TestSectionsEnabled(TestCase):
    """Verifica que sections desabilitadas retornam 404."""

    def setUp(self):
        super().setUp()
        self.category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica-sec")
        self.provider = make_user(role=CustomUser.Role.PRESTADOR)
        self.service = Service.objects.create(
            name="Instalação",
            slug="instalacao-sec",
            base_price=10,
            category=self.category,
            created_by=self.provider,
        )

    def test_services_list_404_when_disabled(self):
        settings = SiteSettings.load()
        settings.services_enabled = False
        settings.save(update_fields=["services_enabled"])
        response = self.client.get(reverse("services-list"))
        assert response.status_code == 404
