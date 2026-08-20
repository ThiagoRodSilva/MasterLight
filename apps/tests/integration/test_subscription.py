"""Integração ponta a ponta: Subscription (plano de manutenção) completo."""

import json
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.checkout.models import Order
from apps.services.models import MaintenancePlan, MaintenancePlanTemplate, ServiceCategory
from apps.tests.helpers import AsaasMockMixin, make_user

ASAAS_SETTINGS = {
    "PAYMENT_PROVIDER": "asaas",
    "ASAAS_API_KEY": "teste-key",
    "ASAAS_SANDBOX": True,
    "ASAAS_WEBHOOK_TOKEN": "segredo",
    "CARD_ENABLED": True,
}


@override_settings(**ASAAS_SETTINGS)
class TestMaintenancePlanSubscriptionFlow(AsaasMockMixin, TestCase):
    """Fluxo completo: assinar plano -> pagamento -> primeira visita agendada."""

    def setUp(self):
        super().setUp()
        self.category = ServiceCategory.objects.create(name="Manutenção", slug="manutencao-flow")
        self.provider = make_user(role="prestador", email="provider-sub@test.com")
        self.client_user = make_user(role="cliente", email="client-sub@test.com")
        # Add CPF, phone, address for Asaas checkout
        self.client_user.cpf = "12345678901"
        self.client_user.telefone = "11999999999"
        self.client_user.save()
        from apps.checkout.models import Address
        Address.objects.create(
            user=self.client_user,
            street="Rua Teste",
            number="123",
            city="São Paulo",
            state="SP",
            zip_code="01000-000",
            country="BR",
            is_active=True,
        )

        self.template = MaintenancePlanTemplate.objects.get(plan_type=MaintenancePlan.PlanType.MONTHLY)

    def _subscribe_plan(self, payment_method="PIX"):
        self.client.force_login(self.client_user)
        response = self.client.post(
            reverse("services-plan-subscribe") + f"?tipo={self.template.plan_type}",
            {"payment_method": payment_method, "prestador": self.provider.id, "plan_type": self.template.plan_type},
            follow=False,  # Don't follow external redirect
        )
        return response

    def _pay_first_payment(self, plan):
        from apps.payments.services import AsaasGateway

        tx = plan.order.transactions.filter(provider="asaas").first()
        if not tx:
            AsaasGateway().subscribe(plan, billing_type="PIX")
            tx = plan.order.transactions.filter(provider="asaas").first()

        # For subscription checkout (RECURRENT), first CHECKOUT_PAID, then PAYMENT_CONFIRMED for first payment
        checkout_id = self.asaas.checkout_id
        payload = json.dumps({"event": "CHECKOUT_PAID", "checkout": {"id": checkout_id, "status": "PAID", "subscription": {"id": plan.asaas_subscription_id}}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        # Check if plan has subscription_id now
        plan.refresh_from_db()

        # Then simulate first subscription payment
        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id, "subscription": plan.asaas_subscription_id, "value": float(plan.value)}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

    def test_subscription_pix_complete_flow(self):
        """Fluxo completo: assinar -> pagamento -> plano ativo -> primeira visita agendada."""
        response = self._subscribe_plan("PIX")
        self.assertEqual(response.status_code, 302)

        plan = MaintenancePlan.objects.get(client=self.client_user)
        self.assertEqual(plan.plan_type, MaintenancePlan.PlanType.MONTHLY)
        # Template value from migration is 79.90
        self.assertEqual(plan.value, Decimal("79.90"))
        self.assertEqual(plan.prestador, self.provider)
        # next_due_date is today + 30 days (cycle_days for monthly)
        from datetime import date, timedelta
        expected_due = date.today() + timedelta(days=30)
        self.assertEqual(plan.next_due_date, expected_due)

        order = plan.order
        self.assertEqual(order.kind, Order.Kind.SUBSCRIPTION)
        self.assertEqual(order.status, Order.Status.AWAITING_PAYMENT)

        self._pay_first_payment(plan)

        plan.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

        from apps.services.models import MaintenanceVisit

        visit = MaintenanceVisit.objects.filter(plan=plan).first()
        self.assertIsNotNone(visit)
        self.assertIsNone(visit.completed_at)
        # Visit should be scheduled at the original next_due_date (before signal advances it)
        from datetime import date, timedelta
        expected_visit_date = date.today() + timedelta(days=30)
        self.assertEqual(visit.scheduled_at.date(), expected_visit_date)
        # Plan's next_due_date should now be advanced by one cycle
        self.assertEqual(plan.next_due_date, expected_visit_date + timedelta(days=30))


    def test_subscription_requires_client_role(self):
        """Apenas clientes podem assinar planos."""
        self.client.force_login(self.provider)
        response = self.client.post(
            reverse("services-plan-subscribe") + f"?tipo={self.template.plan_type}",
            {"payment_method": "PIX", "prestador": self.provider.id},
        )
        self.assertEqual(response.status_code, 403)

    def test_subscription_template_must_be_active(self):
        """Template inativo não pode ser assinado."""
        self.template.is_active = False
        self.template.save()

        self.client.force_login(self.client_user)
        response = self.client.post(
            reverse("services-plan-subscribe") + f"?tipo={self.template.plan_type}",
            {"payment_method": "PIX", "prestador": self.provider.id, "plan_type": self.template.plan_type},
        )
        # Form validation error should cause re-render with error (200)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "indisponível")

    def test_subscription_recurring_payments_webhook(self):
        """Webhooks de renovações (PAYMENT_CONFIRMED) agendam visitas."""
        response = self._subscribe_plan("PIX")
        self.assertEqual(response.status_code, 302)
        plan = MaintenancePlan.objects.get(client=self.client_user)
        self._pay_first_payment(plan)

        from apps.payments.services import AsaasGateway

        for _ in range(3):
            payload = json.dumps(
                {
                    "event": "PAYMENT_CONFIRMED",
                    "payment": {"id": f"pay_renewal_{_}", "subscription": plan.asaas_subscription_id, "value": float(plan.value)},
                }
            )
            AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        plan.refresh_from_db()
        from apps.services.models import MaintenanceVisit

        visits = MaintenanceVisit.objects.filter(plan=plan).count()
        self.assertEqual(visits, 4)


@override_settings(**ASAAS_SETTINGS)
class TestSubscriptionPlanList(AsaasMockMixin, TestCase):
    """Testes de listagem pública de planos."""

    def test_plan_list_shows_active_only(self):
        """Lista pública mostra apenas templates ativos."""
        response = self.client.get(reverse("services-plan-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manutenção mensal")
        self.assertContains(response, "Manutenção trimestral")
        self.assertContains(response, "Manutenção anual")

    def test_plan_list_section_disabled_404(self):
        """Se manutenção desativada em SiteSettings, retorna 404."""
        from apps.core.models import SiteSettings

        settings = SiteSettings.objects.get(pk=1)
        settings.maintenance_enabled = False
        settings.save()

        response = self.client.get(reverse("services-plan-list"))
        self.assertEqual(response.status_code, 404)
