"""Testes de idempotencia e validacoes extras para Services."""

from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.checkout.models import Order
from apps.core.models import SiteSettings
from apps.services.models import (
    MaintenancePlan,
    MaintenancePlanTemplate,
    Service,
    ServiceCategory,
    ServiceRequest,
)
from apps.tests.helpers import make_user


class TestIdempotency(TestCase):
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

    def test_double_post_subscribe_creates_single_plan(self):
        """Duplo POST em services-plan-subscribe deve criar apenas 1 MaintenancePlan + 1 Order."""
        prestador = make_user(role=CustomUser.Role.PRESTADOR)
        self.client.force_login(self.cliente)

        # Primeiro POST
        response1 = self.client.post(
            reverse("services-plan-subscribe"),
            {"plan_type": "mensal", "prestador": prestador.pk},
        )
        assert response1.status_code == 302
        plan1 = MaintenancePlan.objects.get(client=self.cliente)
        order1 = plan1.order
        assert MaintenancePlan.objects.filter(client=self.cliente, is_active=True).count() == 1
        assert Order.objects.filter(user=self.cliente, kind=Order.Kind.SUBSCRIPTION).count() == 1

        # Segundo POST (duplo submit ou voltar a pagina e submeter novamente)
        response2 = self.client.post(
            reverse("services-plan-subscribe"),
            {"plan_type": "mensal", "prestador": prestador.pk},
        )
        assert response2.status_code == 302
        # Deve redirecionar com mensagem de erro
        assert MaintenancePlan.objects.filter(client=self.cliente, is_active=True).count() == 1
        assert Order.objects.filter(user=self.cliente, kind=Order.Kind.SUBSCRIPTION).count() == 1
        plan2 = MaintenancePlan.objects.get(client=self.cliente)
        assert plan2 == plan1
        assert plan2.order == order1


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


class TestFinalPriceZero(TestCase):
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

    @override_settings(PAYMENT_PROVIDER="manual")
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


class TestCancelRequestCancelsOrder(TestCase):
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

    @override_settings(PAYMENT_PROVIDER="manual")
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


class TestMaintenancePlanTemplateUniqueConstraint(TestCase):
    """Teste da constraint unique em MaintenancePlanTemplate.plan_type (is_active=True)."""

    def setUp(self):
        super().setUp()
        # Delete seed plans to avoid unique constraint conflicts
        MaintenancePlanTemplate.objects.all().delete()

    def test_duplicate_active_plan_type_raises_integrity_error(self):
        """Dois templates ativos com mesmo plan_type devem falhar com IntegrityError."""
        MaintenancePlanTemplate.objects.create(
            name="Plano Mensal 1",
            plan_type="mensal",
            value="79.90",
            is_active=True,
        )
        # Segundo template ativo com mesmo plan_type deve falhar
        with self.assertRaises(IntegrityError):
            MaintenancePlanTemplate.objects.create(
                name="Plano Mensal 2",
                plan_type="mensal",
                value="99.90",
                is_active=True,
            )

    def test_inactive_duplicate_plan_type_allowed(self):
        """Template inativo com mesmo plan_type de ativo deve ser permitido."""
        MaintenancePlanTemplate.objects.create(
            name="Plano Mensal Ativo",
            plan_type="mensal",
            value="79.90",
            is_active=True,
        )
        # Inativo com mesmo plan_type deve ser permitido
        template2 = MaintenancePlanTemplate.objects.create(
            name="Plano Mensal Inativo",
            plan_type="mensal",
            value="99.90",
            is_active=False,
        )
        assert template2.pk is not None


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

    def test_get_visit_complete_returns_405(self):
        """GET em services-visit-complete deve retornar 405 (nao 500)."""
        from apps.checkout.models import Order
        order = Order.objects.create(user=self.cliente, status=Order.Status.PAID, kind=Order.Kind.SUBSCRIPTION)
        plan = MaintenancePlan.objects.create(
            plan_type="mensal",
            value="79.90",
            next_due_date="2025-01-01",
            client=self.cliente,
            prestador=self.provider,
            order=order,
        )
        from django.utils import timezone

        from apps.services.models import MaintenanceVisit
        visit = MaintenanceVisit.objects.create(plan=plan, scheduled_at=timezone.now())
        self.client.force_login(self.provider)
        response = self.client.get(reverse("services-visit-complete", kwargs={"pk": visit.pk}))
        assert response.status_code == 405


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

    def test_maintenance_list_404_when_disabled(self):
        settings = SiteSettings.load()
        settings.maintenance_enabled = False
        settings.save(update_fields=["maintenance_enabled"])
        response = self.client.get(reverse("services-plan-list"))
        assert response.status_code == 404

