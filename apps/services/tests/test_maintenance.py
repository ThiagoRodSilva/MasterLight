"""Testes do fluxo de manutenção elétrica (planos recorrentes)."""

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.checkout.models import Order
from apps.core.models import SiteSettings
from apps.payments.models import Transaction
from apps.payments.services import AsaasGateway
from apps.services.models import MaintenancePlan, MaintenanceVisit
from conftest import UserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("activation")]


@pytest.fixture
def cliente(db):
    return UserFactory(role=CustomUser.Role.CLIENTE)


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


class TestMaintenancePlanModel:
    def test_cycle_days(self):
        assert MaintenancePlan.PlanType.MONTHLY in "mensal"
        plan = MaintenancePlan(plan_type="trimestral")
        assert plan.cycle_days() == 90

    def test_cycle_days_for(self):
        assert MaintenancePlan.cycle_days_for("mensal") == 30
        assert MaintenancePlan.cycle_days_for("trimestral") == 90
        assert MaintenancePlan.cycle_days_for("anual") == 365

    def test_str(self, cliente):
        plan = _make_plan(cliente)
        assert "Manutenção" in str(plan)


class TestSubscribeManual:
    def test_manual_subscribe_creates_pending_transaction(self, client, cliente):
        from django.test import override_settings

        prestador = UserFactory(role=CustomUser.Role.PRESTADOR)
        with override_settings(PAYMENT_PROVIDER="manual"):
            client.force_login(cliente)
            resp = client.post(
                "/servicos/planos/assinar/", {"plan_type": "mensal", "prestador": prestador.pk}
            )
        assert resp.status_code == 302
        plan = MaintenancePlan.objects.get(client=cliente)
        tx = Transaction.objects.get(order=plan.order)
        assert tx.status == Transaction.Status.PENDING
        assert tx.amount == Decimal("79.90")

    def test_subscribe_next_due_respects_cycle(self, client):
        from django.test import override_settings

        cliente = UserFactory(role=CustomUser.Role.CLIENTE)
        prestador = UserFactory(role=CustomUser.Role.PRESTADOR)
        with override_settings(PAYMENT_PROVIDER="manual"):
            client.force_login(cliente)
            client.post(
                "/servicos/planos/assinar/",
                {"plan_type": "trimestral", "prestador": prestador.pk},
            )
        plan = MaintenancePlan.objects.get(client=cliente)
        expected = timezone.localdate() + timedelta(days=90)
        assert plan.next_due_date == expected

    def test_credit_card_subscribe_graceful_on_manual(self, client, cliente):
        from django.test import override_settings

        prestador = UserFactory(role=CustomUser.Role.PRESTADOR)
        with override_settings(PAYMENT_PROVIDER="manual"):
            client.force_login(cliente)
            resp = client.post(
                "/servicos/planos/assinar/",
                {
                    "plan_type": "mensal",
                    "prestador": prestador.pk,
                    "payment_method": "CREDIT_CARD",
                },
            )
        assert resp.status_code == 302
        assert not MaintenancePlan.objects.filter(client=cliente).exists()

    def test_paid_transaction_schedules_first_visit(self, cliente):

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


class TestAsaasSubscribe:
    def test_asaas_subscribe_createssubscription(self, cliente, asaas):
        prestador = UserFactory(role=CustomUser.Role.PRESTADOR)
        plan = _make_plan(cliente, prestador=prestador)
        result = AsaasGateway().subscribe(plan)
        assert result.ok
        assert result.subscription_id == "sub_0001"
        plan.refresh_from_db()
        assert plan.asaas_subscription_id == "sub_0001"
        tx = Transaction.objects.get(order=plan.order)
        assert tx.external_id == asaas.payment_id

    def test_webhook_schedules_visit(self, cliente, asaas):
        prestador = UserFactory(role=CustomUser.Role.PRESTADOR)
        plan = _make_plan(cliente, prestador=prestador)
        original_due = plan.next_due_date
        AsaasGateway().subscribe(plan)
        tx = Transaction.objects.get(order=plan.order)
        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": asaas.payment_id}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID
        visit = MaintenanceVisit.objects.get(plan=plan)
        assert visit.scheduled_at.date() == original_due


class TestMaintenanceViews:
    def test_plan_list_200_when_enabled(self, client):
        resp = client.get("/servicos/planos/")
        assert resp.status_code == 200
        assert "Assinatura" in resp.content.decode()

    def test_plan_list_404_when_disabled(self, client):
        settings = SiteSettings.load()
        settings.maintenance_enabled = False
        settings.save(update_fields=["maintenance_enabled"])
        resp = client.get("/servicos/planos/")
        assert resp.status_code == 404

    def test_plan_form_requires_login(self, client):
        resp = client.get("/servicos/planos/assinar/")
        assert resp.status_code == 302

    def test_visits_dashboard_requires_provider(self, client, cliente):
        prestador = UserFactory(role=CustomUser.Role.PRESTADOR)
        plan = _make_plan(cliente, prestador)
        MaintenanceVisit.objects.create(plan=plan, scheduled_at=timezone.now())
        client.force_login(cliente)
        resp = client.get("/servicos/visitas/")
        assert resp.status_code == 403


class TestVisitCompleteView:
    def test_complete_marks_visit(self, client):
        prestador = UserFactory(role=CustomUser.Role.PRESTADOR)
        cliente = UserFactory(role=CustomUser.Role.CLIENTE)
        plan = _make_plan(cliente, prestador)
        visit = MaintenanceVisit.objects.create(plan=plan, scheduled_at=timezone.now())
        client.force_login(prestador)
        resp = client.post(f"/servicos/visitas/{visit.pk}/concluir/")
        assert resp.status_code == 302
        visit.refresh_from_db()
        assert visit.completed_at is not None
