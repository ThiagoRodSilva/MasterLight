"""Testes do fluxo de manutenção elétrica (planos recorrentes)."""

import json
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.checkout.models import Order
from apps.core.models import SiteSettings
from apps.payments.models import Transaction
from apps.payments.services import AsaasGateway
from apps.services.models import MaintenancePlan, MaintenanceVisit
from apps.tests.helpers import AsaasMockMixin, make_user, mock_asaas

ASAAS_SETTINGS = {
    "PAYMENT_PROVIDER": "asaas",
    "ASAAS_API_KEY": "teste-key",
    "ASAAS_SANDBOX": True,
    "ASAAS_WEBHOOK_TOKEN": "segredo",
}


def _make_plan(cliente, prestador=None, plan_type="mensal"):
    order = Order.objects.create(
        user=cliente, status=Order.Status.AWAITING_PAYMENT, kind=Order.Kind.SUBSCRIPTION
    )
    return MaintenancePlan.objects.create(
        plan_type=plan_type,
        value="79.90",
        next_due_date=date.today() + timedelta(days=30),
        client=cliente,
        prestador=prestador,
        order=order,
    )


def _make_cliente():
    return make_user(role=CustomUser.Role.CLIENTE)


def _make_prestador():
    return make_user(role=CustomUser.Role.PRESTADOR)


class TestMaintenancePlanModel(TestCase):
    def test_cycle_days(self):
        assert MaintenancePlan.PlanType.MONTHLY in "mensal"
        plan = MaintenancePlan(plan_type="trimestral")
        assert plan.cycle_days() == 90

    def test_cycle_days_for(self):
        assert MaintenancePlan.cycle_days_for("mensal") == 30
        assert MaintenancePlan.cycle_days_for("trimestral") == 90
        assert MaintenancePlan.cycle_days_for("anual") == 365

    def test_str(self):
        plan = _make_plan(_make_cliente())
        assert "Manutenção" in str(plan)


class TestSubscribeManual(TestCase):
    def test_manual_subscribe_creates_pending_transaction(self):
        prestador = _make_prestador()
        cliente = _make_cliente()
        with override_settings(PAYMENT_PROVIDER="manual"):
            self.client.force_login(cliente)
            resp = self.client.post(
                "/servicos/planos/assinar/", {"plan_type": "mensal", "prestador": prestador.pk}
            )
        assert resp.status_code == 302
        plan = MaintenancePlan.objects.get(client=cliente)
        tx = Transaction.objects.get(order=plan.order)
        assert tx.status == Transaction.Status.PENDING
        assert tx.amount == Decimal("79.90")

    def test_subscribe_next_due_respects_cycle(self):
        cliente = _make_cliente()
        prestador = _make_prestador()
        with override_settings(PAYMENT_PROVIDER="manual"):
            self.client.force_login(cliente)
            self.client.post(
                "/servicos/planos/assinar/",
                {"plan_type": "trimestral", "prestador": prestador.pk},
            )
        plan = MaintenancePlan.objects.get(client=cliente)
        expected = timezone.localdate() + timedelta(days=90)
        assert plan.next_due_date == expected

    def test_credit_card_subscribe_graceful_on_manual(self):
        prestador = _make_prestador()
        cliente = _make_cliente()
        with override_settings(PAYMENT_PROVIDER="manual"):
            self.client.force_login(cliente)
            resp = self.client.post(
                "/servicos/planos/assinar/",
                {
                    "plan_type": "mensal",
                    "prestador": prestador.pk,
                    "payment_method": "CREDIT_CARD",
                },
            )
        assert resp.status_code == 302
        assert not MaintenancePlan.objects.filter(client=cliente).exists()

    @override_settings(**ASAAS_SETTINGS)
    def test_subscribe_asaas_creates_hosted_checkout(self):
        from apps.checkout.models import Address

        prestador = _make_prestador()
        cliente = _make_cliente()
        Address.objects.create(
            user=cliente,
            street="Rua A",
            number="10",
            city="Cidade",
            state="SP",
            zip_code="01001000",
            country="BR",
        )
        cliente.cpf = "12345678901"
        cliente.telefone = "11999999999"
        cliente.save(update_fields=["cpf", "telefone"])
        with mock_asaas() as fake:
            self.client.force_login(cliente)
            resp = self.client.post(
                "/servicos/planos/assinar/",
                {"plan_type": "mensal", "prestador": prestador.pk},
            )
        assert resp.status_code == 302
        assert resp.url == fake.checkout_url
        plan = MaintenancePlan.objects.get(client=cliente)
        tx = Transaction.objects.get(order=plan.order)
        assert tx.status == Transaction.Status.PENDING
        assert tx.provider == "asaas"
        assert tx.external_id == fake.checkout_id
        checkout_call = next(
            c for c in fake.calls if c["method"] == "POST" and c["url"].endswith("/checkouts")
        )
        assert checkout_call["body"]["chargeTypes"] == ["RECURRENT"]
        assert checkout_call["body"]["billingTypes"] == ["CREDIT_CARD"]
        assert checkout_call["body"]["subscription"]["cycle"] == "MONTHLY"

    @override_settings(**ASAAS_SETTINGS)
    def test_subscribe_asaas_checkout_paid_links_subscription(self):
        prestador = _make_prestador()
        cliente = _make_cliente()
        with mock_asaas() as fake:
            self.client.force_login(cliente)
            resp = self.client.post(
                "/servicos/planos/assinar/",
                {"plan_type": "trimestral", "prestador": prestador.pk},
            )
            assert resp.status_code == 302
            plan = MaintenancePlan.objects.get(client=cliente)
            tx = Transaction.objects.get(order=plan.order)

            payload = json.dumps(
                {
                    "event": "CHECKOUT_PAID",
                    "checkout": {
                        "id": fake.checkout_id,
                        "externalReference": str(plan.order.pk),
                        "subscription": {"cycle": "QUARTERLY"},
                    },
                }
            )
            AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

            tx.refresh_from_db()
            plan.refresh_from_db()
        assert tx.status == Transaction.Status.PAID
        assert plan.asaas_subscription_id == fake.checkout_subscription_id

    def test_paid_transaction_schedules_first_visit(self):
        cliente = _make_cliente()
        plan = _make_plan(cliente)
        original_due = plan.next_due_date
        tx = Transaction.objects.create(
            order=plan.order, user=cliente, provider="manual", amount=plan.value, status="pending"
        )
        tx.status = Transaction.Status.PAID
        tx.save(update_fields=["status", "updated_at"])
        visit = MaintenanceVisit.objects.get(plan=plan)
        assert visit.scheduled_at.date() == original_due
        plan.refresh_from_db()
        assert plan.next_due_date == original_due + timedelta(days=30)


@override_settings(**ASAAS_SETTINGS)
class TestAsaasSubscribe(AsaasMockMixin, TestCase):
    def test_asaas_subscribe_createssubscription(self):
        prestador = _make_prestador()
        cliente = _make_cliente()
        plan = _make_plan(cliente, prestador=prestador)
        result = AsaasGateway().subscribe(plan)
        assert result.ok
        assert result.subscription_id == "sub_0001"
        plan.refresh_from_db()
        assert plan.asaas_subscription_id == "sub_0001"
        tx = Transaction.objects.get(order=plan.order)
        assert tx.external_id == self.asaas.payment_id

    def test_webhook_schedules_visit(self):
        prestador = _make_prestador()
        cliente = _make_cliente()
        plan = _make_plan(cliente, prestador=prestador)
        original_due = plan.next_due_date
        AsaasGateway().subscribe(plan)
        tx = Transaction.objects.get(order=plan.order)
        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID
        visit = MaintenanceVisit.objects.get(plan=plan)
        assert visit.scheduled_at.date() == original_due


class TestMaintenanceViews(TestCase):
    def test_plan_list_200_when_enabled(self):
        resp = self.client.get("/servicos/planos/")
        assert resp.status_code == 200
        assert "Assinatura" in resp.content.decode()

    def test_plan_list_404_when_disabled(self):
        settings = SiteSettings.load()
        settings.maintenance_enabled = False
        settings.save(update_fields=["maintenance_enabled"])
        resp = self.client.get("/servicos/planos/")
        assert resp.status_code == 404

    def test_plan_form_requires_login(self):
        resp = self.client.get("/servicos/planos/assinar/")
        assert resp.status_code == 302

    def test_plan_form_prefills_tipo_valid(self):
        cliente = _make_cliente()
        self.client.force_login(cliente)
        resp = self.client.get("/servicos/planos/assinar/?tipo=trimestral")
        assert resp.status_code == 200
        assert "trimestral" in resp.content.decode()

    def test_plan_form_ignores_invalid_tipo(self):
        cliente = _make_cliente()
        self.client.force_login(cliente)
        resp = self.client.get("/servicos/planos/assinar/?tipo=inexistente")
        assert resp.status_code == 200

    def test_visits_dashboard_lists_for_provider(self):
        prestador = _make_prestador()
        cliente = _make_cliente()
        plan = _make_plan(cliente, prestador)
        MaintenanceVisit.objects.create(plan=plan, scheduled_at=timezone.now())
        self.client.force_login(prestador)
        resp = self.client.get("/servicos/visitas/")
        assert resp.status_code == 200

    def test_visits_dashboard_requires_provider(self):
        prestador = _make_prestador()
        cliente = _make_cliente()
        plan = _make_plan(cliente, prestador)
        MaintenanceVisit.objects.create(plan=plan, scheduled_at=timezone.now())
        self.client.force_login(cliente)
        resp = self.client.get("/servicos/visitas/")
        assert resp.status_code == 403


class TestVisitCompleteView(TestCase):
    def test_complete_marks_visit(self):
        prestador = _make_prestador()
        cliente = _make_cliente()
        plan = _make_plan(cliente, prestador)
        visit = MaintenanceVisit.objects.create(plan=plan, scheduled_at=timezone.now())
        self.client.force_login(prestador)
        resp = self.client.post(f"/servicos/visitas/{visit.pk}/concluir/")
        assert resp.status_code == 302
        visit.refresh_from_db()
        assert visit.completed_at is not None
