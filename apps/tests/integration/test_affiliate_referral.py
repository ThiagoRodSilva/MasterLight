"""Integração ponta a ponta: Affiliate Referral completo (cookie -> checkout -> comissão)."""

import json
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.affiliate.models import AffiliateProfile, Referral
from apps.checkout.models import Order
from apps.shop.models import Category, Product
from apps.tests.helpers import AsaasMockMixin, make_user

ASAAS_SETTINGS = {
    "PAYMENT_PROVIDER": "asaas",
    "ASAAS_API_KEY": "teste-key",
    "ASAAS_SANDBOX": True,
    "ASAAS_WEBHOOK_TOKEN": "segredo",
    "CARD_ENABLED": True,
}


@override_settings(**ASAAS_SETTINGS)
class TestAffiliateReferralFlow(AsaasMockMixin, TestCase):
    """Fluxo completo: afiliado gera link -> cliente acessa -> compra -> comissão aprovada."""

    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name="Elétrica", slug="eletrica-aff")
        self.product = Product.objects.create(
            name="Produto Afiliado",
            slug="produto-afiliado",
            sku="SKU-AFF",
            price=Decimal("100.00"),
            stock=10,
            category=self.category,
        )
        self.affiliate_user = make_user(role="afiliado", email="afiliado@test.com")
        self.affiliate, _ = AffiliateProfile.objects.get_or_create(
            user=self.affiliate_user, defaults={"commission_rate": Decimal("0.10")}
        )
        self.client_user = make_user(
            role="cliente",
            email="cliente-aff@test.com",
            cpf="12345678901",
            telefone="11999999999",
            address={
                "street": "Rua Teste",
                "number": "123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01000-000",
                "country": "Brasil",
            },
        )

    def _set_ref_cookie(self, code):
        self.client.cookies["ref"] = code

    def _checkout_with_ref(self, payment_method="PIX"):
        session = self.client.session
        session["cart"] = {
            str(self.product.id): {
                "qty": 1,
                "price": float(self.product.price),
                "name": self.product.name,
            }
        }
        session.save()

        self.client.force_login(self.client_user)
        # First GET the checkout page to get CSRF token
        self.client.get(reverse("checkout"))
        response = self.client.post(
            reverse("checkout"),
            {"payment_method": payment_method},
            follow=False,
        )
        return response

    def _pay_order(self, order):
        from apps.payments.services import AsaasGateway

        AsaasGateway().charge(order, billing_type="PIX")
        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

    def test_affiliate_referral_complete_flow(self):
        """Fluxo completo: cookie ref -> checkout -> pagamento -> comissão aprovada."""
        self._set_ref_cookie(self.affiliate.code)
        response = self.client.get(reverse("shop-list"))
        self.assertEqual(response.status_code, 200)

        response = self._checkout_with_ref("PIX")
        self.assertEqual(response.status_code, 302)  # Redirect to Asaas checkout

        order = Order.objects.filter(user=self.client_user).latest("created_at")
        self.assertEqual(order.status, Order.Status.AWAITING_PAYMENT)

        referral = Referral.objects.get(order=order)
        self.assertEqual(referral.affiliate, self.affiliate)
        self.assertEqual(referral.referred, self.client_user)
        self.assertEqual(referral.status, Referral.Status.PENDING)
        self.assertEqual(referral.commission_amount, Decimal("10.00"))

        self._pay_order(order)

        order.refresh_from_db()
        referral.refresh_from_db()
        self.affiliate.refresh_from_db()

        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(referral.status, Referral.Status.APPROVED)
        self.assertEqual(self.affiliate.balance, Decimal("10.00"))

    def test_affiliate_referral_multiple_orders(self):
        """Múltiplos pedidos do mesmo cliente geram múltiplas comissões.

        Skipped in Asaas test class due to mock idempotency issues.
        See TestAffiliateReferralMultipleOrdersManual for manual provider test.
        """
        self.skipTest("Asaas mock idempotency issue - tested in TestAffiliateReferralMultipleOrdersManual")


@override_settings(PAYMENT_PROVIDER="manual")
class TestAffiliateReferralMultipleOrdersManual(TestCase):
    """Teste de múltiplos pedidos com provider manual (evita idempotência do mock Asaas)."""

    def setUp(self):
        self.category = Category.objects.create(name="Elétrica", slug="eletrica-multi")
        self.product = Product.objects.create(
            name="Produto Multi",
            slug="produto-multi",
            sku="SKU-MULTI",
            price=Decimal("100.00"),
            stock=10,
            category=self.category,
        )
        self.affiliate_user = make_user(role="afiliado", email="afiliado-multi@test.com")
        self.affiliate, _ = AffiliateProfile.objects.get_or_create(
            user=self.affiliate_user, defaults={"commission_rate": Decimal("0.10")}
        )
        self.client_user = make_user(
            role="cliente",
            email="cliente-multi@test.com",
            cpf="12345678901",
            telefone="11999999999",
            address={
                "street": "Rua Teste",
                "number": "123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01000-000",
                "country": "Brasil",
            },
        )

    def _set_ref_cookie(self, code):
        self.client.cookies["ref"] = code

    def _checkout_with_ref(self, payment_method="PIX"):
        session = self.client.session
        session["cart"] = {
            str(self.product.id): {
                "qty": 1,
                "price": float(self.product.price),
                "name": self.product.name,
            }
        }
        session.save()

        self.client.force_login(self.client_user)
        self.client.get(reverse("checkout"))
        response = self.client.post(
            reverse("checkout"),
            {"payment_method": payment_method},
            follow=False,
        )
        return response

    def test_affiliate_referral_multiple_orders_manual(self):
        """Múltiplos pedidos do mesmo cliente geram múltiplas comissões (provider manual)."""
        self._set_ref_cookie(self.affiliate.code)

        for _i in range(3):
            response = self._checkout_with_ref("PIX")
            self.assertEqual(response.status_code, 302)

            order = Order.objects.filter(user=self.client_user).latest("created_at")
            # Manual payment: approve the transaction directly
            tx = order.transactions.first()
            tx.status = "paid"
            tx.save(update_fields=["status", "updated_at"])

        self.affiliate.refresh_from_db()
        self.assertEqual(self.affiliate.balance, Decimal("30.00"))
        self.assertEqual(Referral.objects.filter(affiliate=self.affiliate).count(), 3)


@override_settings(**ASAAS_SETTINGS)
class TestAffiliateDashboardFlow(AsaasMockMixin, TestCase):
    """Fluxo do dashboard do afiliado: visualizar comissões, cadastrar Pix, solicitar saque."""

    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name="Elétrica", slug="eletrica-dash")
        self.product = Product.objects.create(
            name="Produto Dash",
            slug="produto-dash",
            sku="SKU-DASH",
            price=Decimal("200.00"),
            stock=5,
            category=self.category,
        )
        self.affiliate_user = make_user(role="afiliado", email="afiliado-dash@test.com")
        self.affiliate, _ = AffiliateProfile.objects.get_or_create(
            user=self.affiliate_user, defaults={"commission_rate": Decimal("0.10")}
        )
        self.client_user = make_user(
            role="cliente",
            email="cliente-dash@test.com",
            cpf="12345678901",
            telefone="11999999999",
            address={
                "street": "Rua Teste",
                "number": "123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01000-000",
                "country": "Brasil",
            },
        )

    def _set_ref_cookie(self, code):
        self.client.cookies["ref"] = code

    def _checkout_with_ref(self, payment_method="PIX"):
        session = self.client.session
        session["cart"] = {
            str(self.product.id): {
                "qty": 1,
                "price": float(self.product.price),
                "name": self.product.name,
            }
        }
        session.save()

        self.client.force_login(self.client_user)
        # First GET the checkout page to get CSRF token
        self.client.get(reverse("checkout"))
        response = self.client.post(
            reverse("checkout"),
            {"payment_method": payment_method},
            follow=False,
        )
        return response

    def _generate_commission(self):
        self._set_ref_cookie(self.affiliate.code)
        response = self._checkout_with_ref("PIX")
        self.assertEqual(response.status_code, 302)

        order = Order.objects.filter(user=self.client_user).latest("created_at")
        self._pay_order(order)

    def _pay_order(self, order):
        from apps.payments.services import AsaasGateway

        AsaasGateway().charge(order, billing_type="PIX")
        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

    def test_affiliate_dashboard_shows_commissions(self):
        """Dashboard mostra comissões pendentes e aprovadas."""
        self._generate_commission()

        self.client.force_login(self.affiliate_user)
        response = self.client.get(reverse("affiliate-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "R$ 20,00")
        self.assertContains(response, "Aprovada")

    def test_affiliate_can_register_pix_key(self):
        """Afiliado pode cadastrar chave Pix no dashboard."""
        self.client.force_login(self.affiliate_user)
        response = self.client.post(
            reverse("affiliate-pix-key"),
            {"pix_key": "chave-pix-teste@email.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chave Pix cadastrada com sucesso")

        self.affiliate.refresh_from_db()
        self.assertEqual(self.affiliate.pix_key, "chave-pix-teste@email.com")

    def test_affiliate_withdrawal_blocked_without_pix(self):
        """Saque bloqueado sem chave Pix cadastrada."""
        self._generate_commission()

        self.client.force_login(self.affiliate_user)
        response = self.client.post(reverse("affiliate-payout"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cadastre sua <strong>chave Pix</strong>")

    def test_affiliate_withdrawal_success(self):
        """Saque bem-sucedido com chave Pix cadastrada."""
        self._generate_commission()

        self.affiliate.refresh_from_db()
        self.affiliate.pix_key = "chave-pix@test.com"
        self.affiliate.save(update_fields=["pix_key", "updated_at"])

        self.client.force_login(self.affiliate_user)
        response = self.client.post(reverse("affiliate-payout"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Solicitação de saque criada.")

        self.affiliate.refresh_from_db()
        self.assertEqual(self.affiliate.balance, Decimal("0.00"))

    def test_affiliate_landing_page(self):
        """Landing page pública de afiliados acessível."""
        response = self.client.get(reverse("affiliate-landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Seja um Afiliado")


@override_settings(**ASAAS_SETTINGS)
class TestAffiliateSectionToggle(AsaasMockMixin, TestCase):
    """Afiliados desativados por SiteSettings retornam 404."""

    def test_affiliate_landing_404_when_disabled(self):
        from apps.core.models import SiteSettings

        settings = SiteSettings.objects.get(pk=1)
        settings.affiliates_enabled = False
        settings.save()

        response = self.client.get(reverse("affiliate-landing"))
        self.assertEqual(response.status_code, 404)

    def test_affiliate_dashboard_404_when_disabled(self):
        from apps.core.models import SiteSettings

        settings = SiteSettings.objects.get(pk=1)
        settings.affiliates_enabled = False
        settings.save()

        self.client.force_login(make_user(role="afiliado"))
        response = self.client.get(reverse("affiliate-dashboard"))
        self.assertEqual(response.status_code, 404)

    def test_signup_affiliate_option_hidden_when_disabled(self):
        from apps.core.models import SiteSettings

        settings = SiteSettings.objects.get(pk=1)
        settings.affiliates_enabled = False
        settings.save()

        response = self.client.get(reverse("account_signup"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Afiliado")
