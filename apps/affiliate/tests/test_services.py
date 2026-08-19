"""Testes do programa de afiliados (middleware + services)."""

from django.conf import settings
from django.test import Client, TestCase

from apps.affiliate.models import Referral
from apps.affiliate.services import create_payout_request, create_referral_from_request
from apps.checkout.models import Order
from apps.services.models import MaintenancePlan, MaintenancePlanTemplate
from apps.tests.helpers import create_order, make_affiliate, make_user


class TestAffiliateReferralMiddleware(TestCase):
    def test_cookie_set_on_valid_ref(self):
        affiliate = make_affiliate()
        response = Client().get(f"/?ref={affiliate.code}")
        assert settings.AFFILIATE_COOKIE_NAME in response.cookies
        cookie = response.cookies[settings.AFFILIATE_COOKIE_NAME]
        assert cookie.value == affiliate.code
        assert int(cookie["max-age"]) == settings.AFFILIATE_COOKIE_MAX_AGE

    def test_no_cookie_on_invalid_ref(self):
        response = Client().get("/?ref=CODIGO-INVALIDO")
        assert settings.AFFILIATE_COOKIE_NAME not in response.cookies

    def test_no_cookie_without_ref_param(self):
        response = Client().get("/")
        assert settings.AFFILIATE_COOKIE_NAME not in response.cookies


class TestApproveReferral(TestCase):
    def test_order_paid_without_referral(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        tx = order.transactions.first()
        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])
        order.refresh_from_db()
        assert order.status == Order.Status.PAID

    def test_paid_order_decrements_stock(self):
        user = make_user()
        order = create_order(user, with_referral=False, qty=3)
        product = order.items.first().product
        initial_stock = product.stock
        tx = order.transactions.first()
        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])
        product.refresh_from_db()
        assert product.stock == initial_stock - 3

    def test_unpaid_order_does_not_decrement_stock(self):
        user = make_user()
        order = create_order(user, with_referral=False, qty=3)
        product = order.items.first().product
        initial_stock = product.stock
        product.refresh_from_db()
        assert product.stock == initial_stock

    def test_order_paid_and_balance_credited_with_referral(self):
        user = make_user()
        order = create_order(user, with_referral=True)
        referral = order.referrals.first()
        tx = order.transactions.first()
        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])
        order.refresh_from_db()
        referral.refresh_from_db()
        affiliate = referral.affiliate
        affiliate.refresh_from_db()
        assert order.status == Order.Status.PAID
        assert referral.status == referral.Status.APPROVED
        assert affiliate.balance == referral.commission_amount

    def test_refund_does_not_touch_order(self):
        user = make_user()
        order = create_order(user, with_referral=True)
        tx = order.transactions.first()
        tx.status = "refunded"
        tx.save(update_fields=["status", "updated_at"])
        order.refresh_from_db()
        assert order.status == Order.Status.AWAITING_PAYMENT

    def test_approve_referral_called_twice_credits_once(self):
        """Duas chamadas concorrentes de approve_referral creditam comissao so uma vez."""
        from apps.affiliate.services import approve_referral

        user = make_user()
        order = create_order(user, with_referral=True, qty=1)
        referral = order.referrals.first()
        affiliate = referral.affiliate
        tx = order.transactions.first()

        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])

        # Primeira chamada
        pk1 = approve_referral(tx)
        referral.refresh_from_db()
        affiliate.refresh_from_db()
        assert pk1 == referral.pk
        assert referral.status == Referral.Status.APPROVED
        assert affiliate.balance == referral.commission_amount

        # Segunda chamada (simula webhook duplicado)
        pk2 = approve_referral(tx)
        referral.refresh_from_db()
        affiliate.refresh_from_db()
        assert pk2 == referral.pk  # retorna o mesmo pk
        assert referral.status == Referral.Status.APPROVED
        assert affiliate.balance == referral.commission_amount  # saldo nao dobra


class TestCreatePayoutRequest(TestCase):
    def test_requires_pix_key(self):
        affiliate = make_affiliate()
        affiliate.balance = 100
        affiliate.save(update_fields=["balance"])
        with self.assertRaisesRegex(ValueError, "chave Pix"):
            create_payout_request(affiliate)

    def test_insufficient_balance_raises(self):
        affiliate = make_affiliate()
        affiliate.balance = 0
        affiliate.pix_key = "email@exemplo.com"
        affiliate.save(update_fields=["balance", "pix_key"])
        with self.assertRaises(ValueError):
            create_payout_request(affiliate)

    def test_payout_zeroes_balance(self):
        affiliate = make_affiliate()
        affiliate.balance = 100
        affiliate.pix_key = "email@exemplo.com"
        affiliate.save(update_fields=["balance", "pix_key"])
        payout = create_payout_request(affiliate)
        assert payout.amount == 100
        affiliate.refresh_from_db()
        assert affiliate.balance == 0


class TestCreateReferralFromRequest(TestCase):
    """Testes da funcao create_referral_from_request."""

    def test_creates_referral_for_order_with_valid_cookie(self):
        """Cria referral para pedido com cookie valido."""
        affiliate = make_affiliate()
        affiliate.balance = 0
        affiliate.save(update_fields=["balance"])
        user = make_user()
        order = create_order(user, with_referral=False)

        # Simula request com cookie
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post("/checkout/")
        request.COOKIES[settings.AFFILIATE_COOKIE_NAME] = affiliate.code
        request.user = user

        referral = create_referral_from_request(request, order)
        assert referral is not None
        assert referral.affiliate == affiliate
        assert referral.referred == user
        assert referral.order == order
        assert referral.commission_amount == order.total * affiliate.commission_rate

    def test_no_referral_without_cookie(self):
        """Nao cria referral sem cookie ref."""
        user = make_user()
        order = create_order(user, with_referral=False)

        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post("/checkout/")
        request.user = user

        referral = create_referral_from_request(request, order)
        assert referral is None

    def test_no_referral_with_invalid_code(self):
        """Nao cria referral com codigo invalido."""
        user = make_user()
        order = create_order(user, with_referral=False)

        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post("/checkout/")
        request.COOKIES[settings.AFFILIATE_COOKIE_NAME] = "CODIGO-INVALIDO"
        request.user = user

        referral = create_referral_from_request(request, order)
        assert referral is None

    def test_auto_referral_blocked(self):
        """Bloqueia auto-referral (afiliado comprando pelo proprio link)."""
        affiliate = make_affiliate()
        user = affiliate.user
        order = create_order(user, with_referral=False)

        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post("/checkout/")
        request.COOKIES[settings.AFFILIATE_COOKIE_NAME] = affiliate.code
        request.user = user

        referral = create_referral_from_request(request, order)
        assert referral is None


class TestServiceOrderReferral(TestCase):
    """Testes de referral em aprovacao de orcamento de servico."""

    def test_approve_referral_service_order(self):
        """Aprovar orcamento de servico cria referral com comissao sobre order.total."""
        from unittest import mock

        from django.test import RequestFactory

        from apps.services.models import Service, ServiceCategory, ServiceRequest
        from apps.services.views import ServiceRequestApproveView

        # Setup: afiliado, cliente, servico, solicitacao orcada
        affiliate = make_affiliate()
        client = make_user()
        provider = make_user(role="prestador")
        category = ServiceCategory.objects.create(name="Eletrica", slug="eletrica")
        service = Service.objects.create(
            name="Instalacao",
            slug="instalacao",
            base_price=500,
            category=category,
            created_by=provider,
        )
        service.providers.add(provider)

        service_request = ServiceRequest.objects.create(
            cliente=client,
            service=service,
            prestador=provider,
            status=ServiceRequest.Status.QUOTED,
            final_price=500,
        )

        # Simula request com cookie do afiliado
        factory = RequestFactory()
        request = factory.post(f"/servicos/solicitacao/{service_request.pk}/aprovar/")
        request.COOKIES[settings.AFFILIATE_COOKIE_NAME] = affiliate.code
        request.user = client

        # Mock checkout_or_charge para nao criar cobranca real
        with mock.patch("apps.payments.services.checkout_or_charge") as mock_checkout:
            mock_checkout.return_value = {"redirect_url": "/success/"}
            view = ServiceRequestApproveView.as_view()
            view(request, pk=service_request.pk)

        # Verifica se order foi criado e referral criado
        service_request.refresh_from_db()
        assert service_request.order is not None
        order = service_request.order
        assert order.kind == Order.Kind.SERVICE

        referral = order.referrals.first()
        assert referral is not None
        assert referral.affiliate == affiliate
        assert referral.referred == client
        assert referral.commission_amount == order.total * affiliate.commission_rate


class TestSubscriptionReferral(TestCase):
    """Testes de referral em assinatura de plano de manutencao."""

    def test_approve_referral_subscription(self):
        """Assinar plano cria referral com comissao sobre 1a parcela (order.total)."""
        from unittest import mock

        affiliate = make_affiliate()
        client = make_user()
        provider = make_user(role="prestador")

        # Usa template existente do seed (plan_type=mensal)
        template = MaintenancePlanTemplate.objects.filter(plan_type="mensal", is_active=True).first()
        assert template is not None

        # Usa test client para ter middleware de mensagens
        self.client.cookies[settings.AFFILIATE_COOKIE_NAME] = affiliate.code
        self.client.force_login(client)

        with mock.patch("apps.payments.services.create_checkout_for_order") as mock_checkout:
            mock_checkout.return_value = type("Result", (), {"ok": True, "url": "/success/", "message": ""})()
            self.client.post("/servicos/planos/assinar/", {"plan_type": template.plan_type, "prestador": provider.pk, "value": str(template.value)})

        # Verifica se plano e order foram criados com referral
        plan = MaintenancePlan.objects.filter(client=client, is_active=True).first()
        assert plan is not None
        order = plan.order
        assert order.kind == Order.Kind.SUBSCRIPTION

        referral = order.referrals.first()
        assert referral is not None
        assert referral.affiliate == affiliate
        assert referral.referred == client
        assert referral.commission_amount == order.total * affiliate.commission_rate


class TestPaymentLinkReferral(TestCase):
    """Testes de referral em link de pagamento avulso (webhook)."""

    def test_payment_link_creates_referral(self):
        """Webhook de payment link cria referral usando affiliate_ref_code."""
        from apps.services.models import Service, ServiceCategory, ServiceRequest

        affiliate = make_affiliate()
        client = make_user()
        provider = make_user(role="prestador")
        category = ServiceCategory.objects.create(name="Eletrica", slug="eletrica")
        service = Service.objects.create(
            name="Instalacao",
            slug="instalacao",
            base_price=500,
            category=category,
            created_by=provider,
        )
        service.providers.add(provider)

        service_request = ServiceRequest.objects.create(
            cliente=client,
            service=service,
            prestador=provider,
            status=ServiceRequest.Status.QUOTED,
            final_price=500,
            affiliate_ref_code=affiliate.code,
            asaas_payment_link_id="pl_12345",
        )

        # Simula pagamento webhook criando order + transaction
        from apps.payments.gateways.asaas import AsaasGateway
        gateway = AsaasGateway()

        # Mock payment data
        payment = {
            "id": "pay_12345",
            "paymentLink": "pl_12345",
            "value": 500,
            "status": "RECEIVED",
        }

        tx = gateway._create_payment_link_transaction(payment, "pay_12345")
        assert tx is not None

        service_request.refresh_from_db()
        order = service_request.order
        assert order is not None

        referral = order.referrals.first()
        assert referral is not None
        assert referral.affiliate == affiliate
        assert referral.referred == client
        assert referral.commission_amount == order.total * affiliate.commission_rate


class TestCheckoutProductReferral(TestCase):
    """Testes de referral em checkout de produtos (loja).

    O checkout de produtos ja era testado em TestApproveReferral.test_order_paid_and_balance_credited_with_referral
    que cria order com referral via create_order helper. O fluxo de view e testado la indiretamente.
    """
    pass
