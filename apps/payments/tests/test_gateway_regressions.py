"""Testes de regressão para bugs de gateway de pagamento Asaas."""

import json
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.checkout.models import Order
from apps.payments.models import Transaction
from apps.payments.services import AsaasGateway
from apps.services.models import Service, ServiceCategory, ServiceRequest
from apps.tests.helpers import AsaasMockMixin, create_order, make_user

ASAAS_SETTINGS = {
    "PAYMENT_PROVIDER": "asaas",
    "ASAAS_API_KEY": "teste-key",
    "ASAAS_SANDBOX": True,
    "ASAAS_WEBHOOK_TOKEN": "segredo",
}


@override_settings(**ASAAS_SETTINGS)
class TestAsaasGatewayRegressions(AsaasMockMixin, TestCase):
    def test_partially_refunded_does_not_refund_order(self):
        """PAYMENT_PARTIALLY_REFUNDED não deve transicionar para REFUNDED."""
        user = make_user()
        order = create_order(user, with_referral=False)
        gateway = AsaasGateway()

        result = gateway.charge(order, billing_type="PIX")
        tx = Transaction.objects.get(pk=result.transaction_id)

        # Confirma pagamento
        payload = json.dumps(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}}
        )
        gateway.webhook(payload, {"x-webhook-token": "segredo"})
        tx.refresh_from_db()
        self.assertEqual(tx.status, Transaction.Status.PAID)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

        # Envia evento de reembolso parcial
        payload = json.dumps(
            {"event": "PAYMENT_PARTIALLY_REFUNDED", "payment": {"id": self.asaas.payment_id}}
        )
        result = gateway.webhook(payload, {"x-webhook-token": "segredo"})
        self.assertTrue(result.ok)
        self.assertIn("informativo", result.message.lower())

        tx.refresh_from_db()
        self.assertEqual(tx.status, Transaction.Status.PAID)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    def test_checkout_webhook_without_transaction_returns_200(self):
        """CHECKOUT_PAID sem transação local deve retornar 200 (não 400)."""
        gateway = AsaasGateway()

        # Checkout ID desconhecido, sem externalReference
        payload = json.dumps({"event": "CHECKOUT_PAID", "checkout": {"id": "chk_desconhecido"}})
        result = gateway.webhook(payload, {"x-webhook-token": "segredo"})

        self.assertTrue(result.ok)
        self.assertIn("sem transação local", result.message)
        self.assertIsNone(result.status)

    def test_payment_link_free_quote_uses_zero(self):
        """ServiceRequest com final_price=0 deve criar OrderItem com unit_price=0."""
        from apps.accounts.models import CustomUser

        prestador = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)

        category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica")
        service = Service.objects.create(
            name="Instalação Grátis",
            base_price=Decimal("100.00"),
            category=category,
            created_by=prestador,
        )
        service.providers.add(prestador)

        # Cria ServiceRequest com final_price=0 (orçamento grátis)
        ServiceRequest.objects.create(
            cliente=cliente,
            service=service,
            prestador=prestador,
            final_price=Decimal("0.00"),
            status=ServiceRequest.Status.QUOTED,
            asaas_payment_link_id="pl_0001",
        )

        gateway = AsaasGateway()

        # Simula webhook PAYMENT_CONFIRMED com paymentLink
        payload = json.dumps(
            {
                "event": "PAYMENT_CONFIRMED",
                "payment": {
                    "id": "pay_link_001",
                    "paymentLink": "pl_0001",
                    "value": "0.00",
                },
            }
        )
        result = gateway.webhook(payload, {"x-webhook-token": "segredo"})

        self.assertTrue(result.ok)
        # Verifica se a transação foi criada
        tx = Transaction.objects.filter(external_id="pay_link_001").first()
        self.assertIsNotNone(tx)

        # Verifica se OrderItem foi criado com unit_price=0
        order = tx.order
        self.assertIsNotNone(order)
        item = order.items.first()
        self.assertIsNotNone(item)
        self.assertEqual(item.unit_price, Decimal("0.00"))

    def test_upsert_transaction_integrity_error_fallback(self):
        """Dupla criação concorrente da mesma transação não deve levantar exceção."""
        user = make_user()
        order = create_order(user, with_referral=False)
        gateway = AsaasGateway()

        # Primeira cobrança
        result1 = gateway.charge(order, billing_type="PIX")
        tx1 = Transaction.objects.get(pk=result1.transaction_id)

        # Simula segundo webhook PAYMENT_CREATED com mesmo external_id
        # (como se fosse retry do Asaas)
        payload = json.dumps(
            {
                "event": "PAYMENT_CREATED",
                "payment": {"id": self.asaas.payment_id, "value": str(order.total)},
            }
        )
        result2 = gateway.webhook(payload, {"x-webhook-token": "segredo"})

        self.assertTrue(result2.ok)
        # Deve ser a mesma transação (idempotente)
        self.assertEqual(result2.transaction_id, str(tx1.pk))
        self.assertEqual(Transaction.objects.filter(external_id=self.asaas.payment_id).count(), 1)

    def test_asaas_webhook_blocks_refunded_to_paid(self):
        """Webhook Asaas não deve permitir transição de REFUNDED para PAID."""
        from apps.accounts.models import CustomUser

        user = make_user(role=CustomUser.Role.CLIENTE)
        order = create_order(user, with_referral=True)
        gateway = AsaasGateway()

        # Cria transação pendente
        result = gateway.charge(order, billing_type="PIX")
        tx = Transaction.objects.get(pk=result.transaction_id)

        # Webhook: paid
        payload = json.dumps(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}}
        )
        result = gateway.webhook(payload, {"x-webhook-token": "segredo"})
        self.assertTrue(result.ok)
        tx.refresh_from_db()
        self.assertEqual(tx.status, Transaction.Status.PAID)

        # Webhook: refunded
        payload = json.dumps(
            {"event": "PAYMENT_REFUNDED", "payment": {"id": self.asaas.payment_id}}
        )
        result = gateway.webhook(payload, {"x-webhook-token": "segredo"})
        self.assertTrue(result.ok)
        tx.refresh_from_db()
        self.assertEqual(tx.status, Transaction.Status.REFUNDED)

        # Webhook: paid novamente (atrasado) - deve ser bloqueado
        payload = json.dumps(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}}
        )
        result = gateway.webhook(payload, {"x-webhook-token": "segredo"})
        self.assertTrue(result.ok)
        self.assertIn("bloqueada", result.message)
        tx.refresh_from_db()
        self.assertEqual(tx.status, Transaction.Status.REFUNDED)

    def test_asaas_refund_blocks_invalid_transition(self):
        """Refund Asaas deve bloquear transição inválida (ex.: de REFUNDED)."""
        from apps.accounts.models import CustomUser

        user = make_user(role=CustomUser.Role.CLIENTE)
        order = create_order(user, with_referral=False)
        gateway = AsaasGateway()

        # Cria transação e marca como PAID via webhook
        result = gateway.charge(order, billing_type="PIX")
        tx = Transaction.objects.get(pk=result.transaction_id)

        payload = json.dumps(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}}
        )
        gateway.webhook(payload, {"x-webhook-token": "segredo"})
        tx.refresh_from_db()
        self.assertEqual(tx.status, Transaction.Status.PAID)

        # Marca como REFUNDED
        payload = json.dumps(
            {"event": "PAYMENT_REFUNDED", "payment": {"id": self.asaas.payment_id}}
        )
        gateway.webhook(payload, {"x-webhook-token": "segredo"})
        tx.refresh_from_db()
        self.assertEqual(tx.status, Transaction.Status.REFUNDED)

        # Tenta refund novamente via API refund() - deve falhar (ok=False)
        result = gateway.refund(tx.pk, order.total)
        self.assertFalse(result.ok)
        self.assertIn("bloqueada", result.message)
        tx.refresh_from_db()
        self.assertEqual(tx.status, Transaction.Status.REFUNDED)
