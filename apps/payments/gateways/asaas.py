"""Gateway real via API v3 do Asaas (Pix, cartão e assinaturas)."""

import json
import logging
import uuid
from datetime import date, timedelta

from django.conf import settings
from django.urls import reverse_lazy

from .asaas_client import AsaasApiClient
from .base import (
    ChargeResult,
    CheckoutResult,
    PaymentGateway,
    PaymentLinkResult,
    WebhookAuthError,
    can_transition,
)
from .base_gateway import BasePaymentGateway

logger = logging.getLogger(__name__)


class AsaasGateway(PaymentGateway, BasePaymentGateway):
    """Gateway real via API v3 do Asaas (Pix e Cartão).

    - `charge` cria cobrança e salva `Transaction.external_id` = id Asaas.
    - `webhook` valida token em `asaas-access-token` (header atual do Asaas) e
      mapeia eventos PAYMENT_CONFIRMED/RECEIVED -> paid, PAYMENT_OVERDUE ->
      failed. `x-webhook-token` é aceito como compatibilidade com integrações
      legadas.
    - Ambiente sandbox/prod controlado por `ASAAS_SANDBOX`.
    """

    name = "asaas"

    # Formas de pagamento aceitas pelo Asaas. DEBIT_CARD usa a mesma mecânica
    # de token do cartão; UNDEFINED deixa o Asaas decidir e TRANSFER depende de
    # transferência manual do cliente. Todos são aceitos no gateway, mas apenas
    # Pix/Cartão são expostos na UI.
    _BILLING_TYPES = {"PIX", "CREDIT_CARD", "DEBIT_CARD", "UNDEFINED", "TRANSFER"}
    _TOKEN_BILLING_TYPES = {"CREDIT_CARD", "DEBIT_CARD"}

    # Eventos informativos: cobrança criada/vencendo/cobrança em andamento não
    # alteram o status financeiro (respondem 200 sem transição).
    _INFORMATIONAL_EVENTS = {
        "payment_due",
        "payment_dunning",
        "payment_restored",
        "payment_received_in_cash_undone",
        "payment_updated",
        "payment_anticipated",
        "payment_awaiting_risk_analysis",
        "payment_approved_by_risk_analysis",
        "payment_bank_slip_viewed",
        "payment_bank_slip_cancelled",
        "payment_checkout_viewed",
        "payment_dunning_requested",
        "payment_dunning_received",
        "payment_refund_in_progress",
        "payment_refund_denied",
        "payment_chargeback_requested",
        "payment_chargeback_dispute",
        "payment_awaiting_chargeback_reversal",
        "payment_split_cancelled",
        "payment_split_divergence_block",
        "payment_split_divergence_block_finished",
        "payment_split_done",
        "checkout_viewed",
        "payment_partially_refunded",
    }
    _AUTHORIZED_EVENTS = {"payment_authorized"}
    _PAID_EVENTS = {"payment_confirmed", "payment_received"}
    _FAILED_EVENTS = {
        "payment_overdue",
        "payment_deleted",
        "payment_failed",
        "payment_reproved_by_risk_analysis",
        "payment_credit_card_capture_refused",
        "payment_credit_card_capture_cancelled",
    }
    _REFUNDED_EVENTS = {
        "payment_refunded",
        "payment_refund_requested",
    }

    def __init__(self):
        self.client = AsaasApiClient()

    _CUSTOMER_MISSING_FIELDS = ("cpfcnpj", "postalcode", "addressnumber", "province", "phonenumber")
    _CUSTOMER_STALE_MARKERS = ("invalid_customer", "customer not found", "customer nao encontrado")

    def _is_customer_error(self, exc: Exception, stale: bool = False) -> bool:
        """True se o erro do Asaas indica problema com o objeto `customer`.

        `stale=True` restringe a marcadores de customer inexistente/inválido
        (usado pelo retry de cache — I6); caso contrário também reconhece a
        resposta de campos obrigatórios ausentes na criação de customer.
        """
        text = str(exc).lower()
        if stale:
            return any(marker in text for marker in self._CUSTOMER_STALE_MARKERS)
        return any(marker in text for marker in self._CUSTOMER_MISSING_FIELDS) or any(
            marker in text for marker in self._CUSTOMER_STALE_MARKERS
        )

    def _build_customer_payload(self, user) -> dict:
        """Monta o payload completo de criação de customer no Asaas (v3).

        A API v3 exige CPF/CNPJ, telefone e endereço para criar um customer;
        preenche com o perfil e o primeiro endereço ativo do usuário quando
        disponíveis. Sem dados o Asaas responde 400 (invalid_object) — o erro é
        traduzido para mensagem amigável em `_ensure_customer`.
        """
        cpf = self.client._sanitize_digits(user.cpf)
        phone = "".join(ch for ch in (user.telefone or "") if ch.isdigit())[:11]
        address = user.addresses.filter(is_active=True).first()

        body: dict = {
            "name": user.get_full_name() or user.username or user.email,
            "email": user.email,
            "externalReference": str(user.pk),
            "notificationDisabled": True,
        }
        if cpf:
            body["cpfCnpj"] = cpf
        if phone:
            body["mobilePhone"] = phone
        if address is not None:
            body["address"] = address.street
            body["addressNumber"] = address.number or ""
            body["province"] = address.state
            body["city"] = address.city
            body["postalCode"] = "".join(ch for ch in address.zip_code if ch.isdigit())
        return body

    def _call_with_customer_retry(self, user, fn):
        """Executa `fn`; se falhar por customer inválido (cache obsoleto), limpa.

        O `asaas_customer_id` em cache pode apontar para um customer excluído no
        Asaas (I6). Nesse caso limpa o cache e tenta uma única vez — o `fn`
        recria o customer. Erros de campos obrigatórios não disparam o retry.
        """
        try:
            return fn()
        except ValueError as exc:
            if self._is_customer_error(exc, stale=True) and getattr(user, "asaas_customer_id", ""):
                logger.info("Asaas: customer %s inválido; recriando.", user.asaas_customer_id)
                user.asaas_customer_id = ""
                user.save(update_fields=["asaas_customer_id"])
                return fn()
            raise

    def _ensure_customer(self, user) -> str:
        """Reutiliza (e salva) o customer_id do Asaas no usuario.

        Busca por e-mail para não duplicar customer (dev/prod reuso), envia
        CPF/telefone/endereço quando existirem e traduz o 400 de campos
        obrigatórios ausentes para uma mensagem amigável. `notificationDisabled`
        evita e-mails automáticos do Asaas fora do fluxo da plataforma.
        """
        cached = getattr(user, "asaas_customer_id", "")
        if cached:
            return cached

        if user.email:
            try:
                result = self.client._api("GET", "customers", params={"email": user.email})
            except ValueError:
                result = {}
            rows = result.get("data") if isinstance(result, dict) else None
            if rows:
                existing = rows[0]
                user.asaas_customer_id = existing["id"]
                user.save(update_fields=["asaas_customer_id"])
                return existing["id"]

        body = self._build_customer_payload(user)
        try:
            customer = self.client._api(
                "POST", "customers", body, idempotency_key=f"customer-{user.pk}"
            )
        except ValueError as exc:
            if self._is_customer_error(exc):
                raise ValueError(
                    "Para realizar o pagamento, cadastre CPF, telefone e endereço "
                    "no seu perfil."
                ) from exc
            raise
        customer_id = customer["id"]
        user.asaas_customer_id = customer_id
        user.save(update_fields=["asaas_customer_id"])
        return customer_id

    def _fetch_pix(self, payment_id: str) -> dict:
        return self.client._api("GET", f"payments/{payment_id}/pixQrCode")

    def _confirmation_url(self, billing_type: str, order_pk) -> str:
        """Escolhe a página de confirmação conforme a forma de pagamento."""
        if billing_type in ("CREDIT_CARD", "DEBIT_CARD"):
            name = "payments-card-confirm"

        else:
            # PIX, UNDEFINED e TRANSFER caem na página do PIX; o polling de
            # status funciona para qualquer cobrança.
            name = "payments-pix-confirm"
        return str(reverse_lazy(name, kwargs={"order_pk": order_pk}))

    def fetch_payment(self, external_id: str) -> dict:
        """Consulta a cobrança atual no Asaas (reconciliação)."""
        return self.client.fetch_payment(external_id)

    def tokenize_credit_card(self, user, card: dict, holder: dict, remote_ip: str = "") -> str:
        """Gera `creditCardToken` no Asaas (tokenização de cartão).

        O token fica vinculado ao customer; cobranças seguintes do mesmo
        cliente podem reusá-lo sem trafegar dados do cartão novamente.
        """
        def _run() -> dict:
            customer = self._ensure_customer(user)
            body = {
                "customer": customer,
                "creditCard": {
                    "holderName": card.get("holder_name", ""),
                    "number": card.get("number", "").strip(),
                    "expiryMonth": str(card.get("expiry_month", "")).strip(),
                    "expiryYear": str(card.get("expiry_year", "")).strip(),
                    "ccv": card.get("ccv", "").strip(),
                },
                "creditCardHolderInfo": {
                    "name": holder.get("name", ""),
                    "email": holder.get("email", ""),
                    "cpfCnpj": holder.get("cpf_cnpj", ""),
                    "postalCode": holder.get("postal_code", ""),
                    "addressNumber": holder.get("address_number", ""),
                    "phone": "".join(ch for ch in (holder.get("phone") or "") if ch.isdigit())[:11],
                },
                "remoteIp": remote_ip,
            }
            return self.client._api(
                "POST",
                "creditCards/tokenizeCreditCard",
                body,
                idempotency_key=f"cardtoken-{user.pk}",
            )

        result = self._call_with_customer_retry(user, _run)
        token = result.get("creditCardToken") or result.get("credit_card_token")
        if not token:
            raise ValueError("Falha ao tokenizar cartão: resposta sem creditCardToken.")
        return token

    def create_payment_link(
        self,
        *,
        name: str,
        value=None,
        description: str = "",
        billing_type: str = "UNDEFINED",
        charge_type: str = "DETACHED",
        due_date_limit_days: int | None = None,
        max_installment_count: int | None = None,
        subscription_cycle: str = "",
        end_date=None,
        external_reference: str = "",
    ) -> PaymentLinkResult:
        """Gera link de pagamento avulso (tela hospedada do Asaas).

        Sem customer: o pagador preenche os dados na página do Asaas
        (`url` retornada). A confirmação chega via webhook com
        `payment.paymentLink` — ainda sem reconcilição local nesta etapa.
        """
        normalized = (billing_type or "UNDEFINED").upper()
        if normalized not in ("UNDEFINED", "CREDIT_CARD", "PIX"):
            raise ValueError(f"billing_type inválido para link: {billing_type}.")
        charge = (charge_type or "DETACHED").upper()
        if charge not in ("DETACHED", "INSTALLMENT", "RECURRENT"):
            raise ValueError(f"charge_type inválido: {charge_type}.")

        body: dict = {"name": name, "billingType": normalized, "chargeType": charge}
        if value is not None:
            body["value"] = self.client._money(value)
        if description:
            body["description"] = description
        # dueDateLimitDays não é necessário (BOLETO removido)
        if charge == "INSTALLMENT" and max_installment_count:
            body["maxInstallmentCount"] = max_installment_count
        if charge == "RECURRENT" and subscription_cycle:
            body["subscriptionCycle"] = subscription_cycle
        if end_date:
            body["endDate"] = end_date.isoformat() if hasattr(end_date, "isoformat") else str(end_date)
        if external_reference:
            body["externalReference"] = external_reference

        link = self.client._api(
            "POST",
            "paymentLinks",
            body,
            idempotency_key=f"paymentlink-{external_reference or uuid.uuid4()}",
        )
        return PaymentLinkResult(
            ok=True,
            url=str(link.get("url") or ""),
            link_id=str(link.get("id") or ""),
            message="Link de pagamento criado.",
        )

    def create_checkout(
        self,
        order,
        *,
        billing_types: list[str] | None = None,
        charge_type: str = "DETACHED",
        callback_urls: dict | None = None,
        cycle: str = "",
        next_due_date=None,
    ) -> CheckoutResult:
        """Cria uma página de pagamento hospedada no Asaas (Checkout).

        Monta items/customerData/callback a partir do pedido, cria a sessão em
        `POST /checkouts` e salva `Transaction.external_id` = id do checkout. A
        confirmação chega via webhook `CHECKOUT_PAID`/`CHECKOUT_EXPIRED` com o
        mesmo `checkout.id` (payload tem `checkout`, não `payment`).

        Em `charge_type=RECURRENT`, o Asaas só aceita `CREDIT_CARD` — o
        `billing_types` é fixado em `["CREDIT_CARD"]` (PIX exige
        DETACHED).
        """
        from apps.payments.models import Transaction

        charge = (charge_type or "DETACHED").upper()
        if charge not in ("DETACHED", "INSTALLMENT", "RECURRENT"):
            raise ValueError(f"charge_type inválido: {charge_type}.")
        if charge == "RECURRENT":
            # API do Asaas: em operações RECURRENT o único método de pagamento
            # permitido é CREDIT_CARD (PIX exige DETACHED). Fixa o
            # billingTypes para não enviar combo inválido e tomar 400.
            normalized = ["CREDIT_CARD"]
        else:
            normalized = [(b or "PIX").upper() for b in (billing_types or ["PIX", "CREDIT_CARD"])]
        invalid = [b for b in normalized if b not in self._BILLING_TYPES]
        if invalid:
            raise ValueError(f"billing_types inválidos: {', '.join(invalid)}.")

        items = []
        for item in order.items.all():
            items.append(
                {
                    "name": item.name[:30],
                    "description": (item.name or item.service.name if item.service else item.name)[:150],
                    "quantity": int(item.qty or 1),
                    "value": float(item.unit_price or 0),
                }
            )
        if not items:
            raise ValueError("Pedido sem itens; não é possível criar o checkout.")

        user = order.user
        full_name = user.get_full_name() or user.username or user.email
        cpf = self.client._sanitize_digits(user.cpf)
        phone = "".join(ch for ch in (user.telefone or "") if ch.isdigit())
        address = user.addresses.filter(is_active=True).first()
        customer_data: dict = {"name": full_name, "email": user.email or ""}
        if cpf:
            customer_data["cpfCnpj"] = cpf
        if phone:
            customer_data["phone"] = phone[:11]
        if address is not None:
            # A API do Asaas exige endereço no customerData (CPF/CNPJ, telefone e
            # endereço completos) para criar o customer do checkout.
            customer_data["postalCode"] = "".join(ch for ch in address.zip_code if ch.isdigit())
            customer_data["address"] = address.street
            customer_data["addressNumber"] = address.number or ""
            customer_data["province"] = address.state
            customer_data["city"] = address.city
        body: dict = {
            "billingTypes": normalized,
            "chargeTypes": [charge],
            "minutesToExpire": 60,
            "externalReference": str(order.pk),
            "items": items,
            "customerData": customer_data,
        }
        if charge == "RECURRENT":
            cycle_map = {
                "mensal": "MONTHLY",
                "trimestral": "QUARTERLY",
                "anual": "YEARLY",
            }
            body["subscription"] = {
                "cycle": cycle_map.get(cycle, "MONTHLY"),
                "nextDueDate": (next_due_date or date.today()).isoformat(),
            }
        if callback_urls:
            body["callback"] = {k: v for k, v in callback_urls.items() if v}

        try:
            checkout = self.client._api(
                "POST", "checkouts", body, idempotency_key=f"checkout-{order.pk}"
            )
        except ValueError as exc:
            if self._is_customer_error(exc):
                raise ValueError(
                    "Para finalizar o pagamento, cadastre CPF, telefone e endereço "
                    "no seu perfil."
                ) from exc
            raise
        checkout_id = str(checkout.get("id") or "")
        url = str(checkout.get("url") or checkout.get("link") or "")
        if not url and checkout_id:
            url = f"https://asaas.com/checkoutSession/show?id={checkout_id}"

        raw = json.dumps({"checkout": checkout})
        self._upsert_transaction(
            order=order,
            user=user,
            external_id=checkout_id,
            amount=order.total,
            status=Transaction.Status.PENDING,
            raw_payload=raw,
            kind=Transaction.Kind.CHECKOUT,
        )
        logger.info("Asaas: checkout %s criado para o pedido %s", checkout_id, order.pk)
        return CheckoutResult(
            ok=True,
            url=url,
            checkout_id=checkout_id,
            message="Checkout hospedado criado.",
        )

    def charge(
        self,
        order,
        billing_type: str = "PIX",
        credit_card_token: str = "",
        remote_ip: str = "",
    ) -> ChargeResult:
        """Gera cobranca (Pix/cartão/etc.) no Asaas e salva Transaction."""
        from apps.payments.models import Transaction

        normalized = (billing_type or "PIX").upper()
        if normalized not in self._BILLING_TYPES:
            raise ValueError(
                f"billing_type inválido: {billing_type} (use {', '.join(sorted(self._BILLING_TYPES))})."
            )

        def _run() -> dict:
            customer = self._ensure_customer(order.user)
            due_date = date.today() + timedelta(days=1)
            body = {
                "customer": customer,
                "billingType": normalized,
                "value": self.client._money(order.total),
                "dueDate": due_date.isoformat(),
            }
            if normalized in self._TOKEN_BILLING_TYPES:
                if not credit_card_token:
                    raise ValueError(f"{normalized} exige um creditCardToken (tokenize primeiro).")
                body["creditCardToken"] = credit_card_token
                if remote_ip:
                    body["remoteIp"] = remote_ip
            return self.client._api(
                "POST", "payments", body, idempotency_key=f"order-{order.pk}"
            )

        payment = self._call_with_customer_retry(order.user, _run)
        extras: dict = {}
        if normalized == "PIX":
            try:
                extras["pix"] = self._fetch_pix(payment["id"])
            except ValueError:
                # QR pode não estar imediatamente disponível no sandbox; segue sem
                # ele e o status é atualizado via webhook/reconciliação.
                logger.warning("Asaas: QR Pix indisponível para o pagamento %s", payment.get("id"))
                extras["pix"] = {}


        raw = json.dumps({"payment": payment, **extras})
        tx = self._upsert_transaction(
            order=order,
            user=order.user,
            external_id=payment["id"],
            amount=order.total,
            status=Transaction.Status.PENDING,
            raw_payload=raw,
        )
        redirect_url = self._confirmation_url(normalized, order.pk)
        logger.info(
            "Asaas: cobrança %s criada para o pedido %s (%s)",
            payment.get("id"), order.pk, normalized,
        )
        return ChargeResult(
            ok=True,
            redirect_url=redirect_url,
            transaction_id=str(tx.pk),
            message=f"Cobrança {normalized} criada para análise.",
            status=Transaction.Status.PENDING,
            raw_payload=raw,
        )

    def subscribe(
        self,
        plan,
        billing_type: str = "PIX",
        credit_card_token: str = "",
        remote_ip: str = "",
    ) -> ChargeResult:
        """Cria assinatura recorrente no Asaas e mapeia a 1ª cobrança."""
        from apps.payments.models import Transaction

        normalized = (billing_type or "PIX").upper()
        if normalized not in self._BILLING_TYPES:
            raise ValueError(
                f"billing_type inválido: {billing_type} (use {', '.join(sorted(self._BILLING_TYPES))})."
            )

        cycle_map = {
            "mensal": "MONTHLY",
            "trimestral": "QUARTERLY",
            "anual": "YEARLY",
        }
        cycle = cycle_map.get(plan.plan_type, "MONTHLY")

        def _run() -> dict:
            customer = self._ensure_customer(plan.client)
            body = {
                "customer": customer,
                "billingType": normalized,
                "value": self.client._money(plan.value),
                "nextDueDate": plan.next_due_date.isoformat(),
                "cycle": cycle,
            }
            if normalized in self._TOKEN_BILLING_TYPES:
                if not credit_card_token:
                    raise ValueError(f"{normalized} exige um creditCardToken (tokenize primeiro).")
                body["creditCardToken"] = credit_card_token
                if remote_ip:
                    body["remoteIp"] = remote_ip
            return self.client._api(
                "POST", "subscriptions", body, idempotency_key=f"plan-{plan.pk}"
            )

        subscription = self._call_with_customer_retry(plan.client, _run)
        subscription_id = subscription["id"]

        # Primeira cobranca da assinatura: usa o id do payment para que o
        # webhook existente (mapeado por Transaction.external_id) o encontre.
        external_payment_id = subscription_id
        first_payment = None
        try:
            payments = self.client._api("GET", f"subscriptions/{subscription_id}/payments")
        except ValueError:
            payments = {}
        rows = payments.get("data") if isinstance(payments, dict) else None
        if rows:
            first_payment = rows[0]
            external_payment_id = first_payment.get("id") or subscription_id

        extras: dict = {}
        if normalized == "PIX":
            try:
                extras["pix"] = self._fetch_pix(external_payment_id)
            except ValueError:
                # Cobrança ainda não possui Pix disponível (ex.: cartão sem emissão
                # imediata); segue sem QR, o status é atualizado via webhook.
                extras["pix"] = {}


        raw = json.dumps(
            {"subscription": subscription, "first_payment": external_payment_id, **extras}
        )
        tx = self._upsert_transaction(
            order=plan.order,
            user=plan.client,
            external_id=external_payment_id,
            amount=plan.value,
            status=Transaction.Status.PENDING,
            raw_payload=raw,
        )

        plan.asaas_subscription_id = subscription_id
        plan.save(update_fields=["asaas_subscription_id", "updated_at"])

        redirect_url = self._confirmation_url(normalized, plan.order.pk)
        logger.info(
            "Asaas: assinatura %s criada para o plano %s (%s)",
            subscription_id, plan.pk, normalized,
        )
        return ChargeResult(
            ok=True,
            redirect_url=redirect_url,
            transaction_id=str(tx.pk),
            message="Assinatura criada. Aguardando o primeiro pagamento.",
            status=Transaction.Status.PENDING,
            raw_payload=raw,
            subscription_id=subscription_id,
        )

    def refund(self, transaction_id, amount) -> ChargeResult:
        from apps.payments.models import Transaction

        tx = Transaction.objects.filter(pk=transaction_id).first()
        if tx is None or not tx.external_id:
            return ChargeResult(ok=False, redirect_url="/", message="Tx não encontrada.")
        try:
            self.client._api(
                "POST", f"payments/{tx.external_id}/refund", {"value": self.client._money(amount)}
            )
        except ValueError:
            return ChargeResult(ok=False, redirect_url="/", message="Falha no reembolso.")
        tx.status = Transaction.Status.REFUNDED
        tx.save(update_fields=["status", "updated_at"])
        return ChargeResult(
            ok=True,
            redirect_url="/",
            transaction_id=str(tx.pk),
            message="Reembolso solicitado.",
        )

    def _create_subscription_transaction(self, payment, external_id):
        """Cria Transaction para uma cobrança de assinatura (renovação).

        Renovações chegam via webhook com um `payment.id` novo, ainda sem
        `Transaction` local. O payload traz `payment.subscription`; mapeamos
        para o `MaintenancePlan.asaas_subscription_id` e abrimos a transação
        pendente ligada ao pedido do plano. Retorna None se não encontrar plano.
        """
        from apps.payments.models import Transaction

        subscription_id = payment.get("subscription") if isinstance(payment, dict) else None
        if not subscription_id:
            return None
        plan = self._find_plan_for_subscription(payment, subscription_id)
        if plan is None or plan.order is None:
            return None
        return self._upsert_transaction(
            order=plan.order,
            user=plan.client,
            external_id=external_id,
            amount=payment.get("value") or plan.value,
            status=Transaction.Status.PENDING,
            raw_payload=json.dumps(payment),
        )

    def _find_plan_for_subscription(self, payment, subscription_id):
        """Localiza o MaintenancePlan de uma cobrança de assinatura.

        Busca primeiro por `asaas_subscription_id`; se ainda não vinculado
        (ex.: Checkout RECURRENT cuja assinatura não foi ligada ao plano),
        usa o `externalReference` da cobrança (= order.pk, herdado do checkout)
        e registra o id da assinatura. Retorna None se não encontrar.
        """
        from apps.services.models import MaintenancePlan

        plan = (
            MaintenancePlan.objects.filter(
                asaas_subscription_id=str(subscription_id), is_active=True
            )
            .select_related("order", "client")
            .first()
        )
        if plan is not None:
            return plan
        if not isinstance(payment, dict):
            return None
        external_ref = payment.get("externalReference") or ""
        try:
            order_pk = uuid.UUID(str(external_ref))
        except (ValueError, TypeError):
            return None
        plan = (
            MaintenancePlan.objects.filter(order__pk=order_pk, is_active=True)
            .select_related("order", "client")
            .first()
        )
        if plan is None:
            return None
        if not plan.asaas_subscription_id:
            plan.asaas_subscription_id = str(subscription_id)
            plan.save(update_fields=["asaas_subscription_id", "updated_at"])
            logger.info(
                "Asaas: assinatura %s vinculada ao plano %s via cobrança",
                subscription_id, plan.pk,
            )
        return plan

    def _resolve_checkout_payment_transaction(self, payment):
        """Resolve um `PAYMENT_*` redundante de Checkout hosted.

        O checkout DETACHED também gera eventos `PAYMENT_*` com `payment.id`
        próprio (≠ id do checkout). O `externalReference` (= order.pk, setado
        em `create_checkout`) localiza a transação do checkout para aplicar o
        status de forma idempotente — o `CHECKOUT_PAID` já confirma, e o
        `PAYMENT_CONFIRMED` apenas reforça sem duplicar nem responder 404.
        """
        from apps.payments.models import Transaction

        external_ref = payment.get("externalReference") if isinstance(payment, dict) else ""
        try:
            order_pk = uuid.UUID(str(external_ref))
        except (ValueError, TypeError):
            return None
        return (
            Transaction.objects.filter(order__pk=order_pk, provider=self.name)
            .order_by("-created_at")
            .first()
        )

    def _create_payment_link_transaction(self, payment, external_id):
        """Cria Transaction para um pagamento vindo de paymentLink avulso.

        O `ServiceRequestPayLinkView` grava `ServiceRequest.asaas_payment_link_id`
        ao gerar o link; o webhook chega com `payment.paymentLink` (id do link).
        Abrimos Order + OrderItem + Transaction pendente ligada à solicitação
        para que o fluxo normal de status (paid) aprove a solicitação via signal.
        Retorna None se nenhuma solicitação corresponder ao link.
        """
        from django.db import transaction as dj_transaction

        from apps.checkout.models import Order, OrderItem
        from apps.payments.models import Transaction
        from apps.services.models import ServiceRequest

        payment_link_id = payment.get("paymentLink") if isinstance(payment, dict) else None
        if not payment_link_id:
            return None
        service_request = (
            ServiceRequest.objects.filter(
                asaas_payment_link_id=str(payment_link_id), is_active=True
            )
            .select_related("service")
            .first()
        )
        if service_request is None or service_request.status != ServiceRequest.Status.QUOTED:
            return None

        with dj_transaction.atomic():
            order = Order.objects.create(
                user=service_request.cliente,
                status=Order.Status.AWAITING_PAYMENT,
                kind=Order.Kind.SERVICE,
            )
            unit_price = (
                service_request.final_price
                if service_request.final_price is not None
                else service_request.service.base_price
            )
            OrderItem.objects.create(
                order=order,
                service=service_request.service,
                name=service_request.service.name,
                qty=1,
                unit_price=unit_price,
            )
            order.recompute_total()
            # Cria referral se houver codigo de afiliado na solicitacao
            if service_request.affiliate_ref_code:
                from django.db import IntegrityError

                from apps.affiliate.models import AffiliateProfile, Referral

                affil = AffiliateProfile.objects.filter(
                    code=service_request.affiliate_ref_code, is_active=True
                ).first()
                if affil and affil.user_id != service_request.cliente_id:
                    try:
                        Referral.objects.create(
                            affiliate=affil,
                            referred=service_request.cliente,
                            order=order,
                            commission_rate=affil.commission_rate,
                            commission_amount=order.total * affil.commission_rate,
                        )
                    except IntegrityError:
                        # Unique constraint violada - referral ja existe para este affiliate+order
                        pass
            service_request.order = order
            service_request.save(update_fields=["order", "updated_at"])

        return self._upsert_transaction(
            order=order,
            user=service_request.cliente,
            external_id=external_id,
            amount=payment.get("value") or order.total,
            status=Transaction.Status.PENDING,
            raw_payload=json.dumps(payment),
        )

    def _handle_checkout_webhook(self, data: dict, checkout: dict, payload_str: str) -> ChargeResult:
        """Processa eventos de Checkout hosted (`CHECKOUT_*`).

        O payload traz `checkout` (não `payment`); `checkout.id` é o
        `Transaction.external_id` gravado na criação. `CHECKOUT_PAID` confirma o
        pagamento; `CHECKOUT_EXPIRED`/`CHECKOUT_CANCELED` marcam como falha. Em
        sessões `RECURRENT`, tentamos capturar o id da assinatura gerada para as
        renovações continuarem via `payment.subscription`.
        """
        from apps.payments.models import Transaction

        event = str(data.get("event") or "").lower()
        checkout_id = str(checkout.get("id") or "")
        tx = Transaction.objects.filter(external_id=checkout_id, provider=self.name).first()

        if tx is None:
            # Fallback por externalReference (order.pk) quando a transação não
            # foi encontrada pelo id do checkout (evento reentrante após troca).
            external_ref = str(checkout.get("externalReference") or "")
            if external_ref:
                tx = (
                    Transaction.objects.filter(
                        order__pk=external_ref, provider=self.name, status=Transaction.Status.PENDING
                    )
                    .order_by("-created_at")
                    .first()
                )
        if tx is None:
            logger.info("Asaas webhook checkout: checkout %s sem transação local; ignorado.", checkout_id)
            return ChargeResult(
                ok=True,
                redirect_url="/",
                message=f"Checkout {checkout_id} sem transação local; ignorado.",
                status=None,
                raw_payload=payload_str,
            )

        if event == "checkout_created":
            tx.raw_payload = payload_str
            tx.save(update_fields=["raw_payload", "updated_at"])
            return ChargeResult(
                ok=True,
                redirect_url="/",
                transaction_id=str(tx.pk),
                message="Checkout criado, aguardando pagamento.",
                status=tx.status,
                raw_payload=payload_str,
            )

        if event in ("checkout_expired", "checkout_canceled"):
            new_status = Transaction.Status.FAILED
        elif event == "checkout_paid":
            new_status = Transaction.Status.PAID
        else:
            logger.info("Asaas webhook checkout: evento '%s' ignorado (sem transição).", event)
            tx.raw_payload = payload_str
            tx.save(update_fields=["raw_payload", "updated_at"])
            return ChargeResult(
                ok=True,
                redirect_url="/",
                transaction_id=str(tx.pk),
                message=f"Checkout evento '{event}' ignorado.",
                status=tx.status,
                raw_payload=payload_str,
            )

        if tx.status != new_status:
            if not can_transition(tx.status, new_status):
                # Evento financeiro que tentaria reverter uma transação terminal
                # (ex.: CHECKOUT_EXPIRED depois de já PAID). Ignora sem transição.
                logger.info(
                    "Asaas webhook checkout: transição %s -> %s bloqueada (%s)",
                    tx.status, new_status, checkout_id,
                )
                return ChargeResult(
                    ok=True,
                    redirect_url="/",
                    transaction_id=str(tx.pk),
                    message=f"Checkout transição '{tx.status} -> {new_status}' bloqueada.",
                    status=tx.status,
                    raw_payload=payload_str,
                )
            tx.status = new_status
            tx.raw_payload = payload_str
            tx.save(update_fields=["status", "raw_payload", "updated_at"])
            logger.info("Asaas webhook checkout: %s -> %s (%s)", event, new_status, checkout_id)

        if new_status == Transaction.Status.PAID:
            self._link_checkout_subscription(checkout_id, tx.order)

        return ChargeResult(
            ok=True,
            redirect_url="/",
            transaction_id=str(tx.pk),
            message=f"Checkout atualizado para {tx.status}.",
            status=tx.status,
            raw_payload=payload_str,
        )

    def _link_checkout_subscription(self, checkout_id: str, order):
        """Captura o id da assinatura gerada por um checkout RECURRENT.

        O webhook `CHECKOUT_PAID` não traz `subscription.id`; consultamos
        `GET /checkouts/{id}` (retorna `subscriptions`) e, como fallback,
        listamos as cobranças do pedido (`GET /payments?externalReference=<pk>`)
        para registrar em `MaintenancePlan.asaas_subscription_id`.
        """
        from apps.services.models import MaintenancePlan

        plan = MaintenancePlan.objects.filter(order=order, is_active=True).first()
        if plan is None or plan.asaas_subscription_id:
            return
        try:
            detail = self.client._api("GET", f"checkouts/{checkout_id}")
        except ValueError:
            detail = {}
        subscriptions = detail.get("subscriptions") if isinstance(detail, dict) else None
        subscription_id = ""
        if isinstance(subscriptions, list) and subscriptions:
            subscription_id = str((subscriptions[0] or {}).get("id") or "")
        if not subscription_id and isinstance(detail, dict):
            sub = detail.get("subscription") if isinstance(detail.get("subscription"), dict) else {}
            subscription_id = str(sub.get("id") or "")

        if not subscription_id:
            # Fallback: a primeira cobrança da assinatura criada pelo checkout
            # herda o externalReference do checkout (= order.pk) e traz o id da
            # assinatura (`subscription`).
            try:
                payments = self.client._api(
                    "GET", "payments", params={"externalReference": str(order.pk), "limit": 20}
                )
            except ValueError:
                payments = {}
            rows = payments.get("data") if isinstance(payments, dict) else None
            if rows:
                for row in rows:
                    if isinstance(row, dict) and row.get("subscription"):
                        subscription_id = str(row["subscription"])
                        break
        if subscription_id:
            plan.asaas_subscription_id = subscription_id
            plan.save(update_fields=["asaas_subscription_id", "updated_at"])
            logger.info("Asaas: assinatura %s vinculada ao plano %s", subscription_id, plan.pk)

    def _handle_subscription_webhook(self, data, subscription, event, payload_str) -> ChargeResult:
        """Processa eventos de assinatura (`SUBSCRIPTION_*`).

        O payload traz `subscription` (sem `payment`/`checkout`). Esses eventos
        não mudam o status financeiro — a cobrança chega depois em `PAYMENT_*` —
        então respondemos 200 sem transição, nunca interrompendo a fila do Asaas.
        No `SUBSCRIPTION_CREATED` aproveitamos o id da assinatura para vincular
        o plano local via `subscription.checkoutSession` (= id do checkout).
        """
        subscription_id = str(subscription.get("id") or "")
        plan = self._link_subscription_to_plan(subscription, subscription_id)
        if plan is None:
            logger.info(
                "Asaas webhook: evento de assinatura '%s' sem plano local (%s).",
                event, subscription_id,
            )
        return ChargeResult(
            ok=True,
            redirect_url="/",
            message=f"Evento de assinatura '{event}' processado sem transição.",
            raw_payload=payload_str,
        )

    def _link_subscription_to_plan(self, subscription, subscription_id):
        """Vincula o id da assinatura Asaas ao MaintenancePlan local.

        Busca primeiro por `asaas_subscription_id` (já vinculado por
        `subscribe()` ou reenvio de webhook) — idempotente. Se ainda não
        vinculado, usa `subscription.checkoutSession` (= id do checkout =
        `Transaction.external_id`) para localizar o plano pelo pedido. Retorna o
        plano (ou None quando não há correspondência).
        """
        from apps.payments.models import Transaction
        from apps.services.models import MaintenancePlan

        plan = (
            MaintenancePlan.objects.filter(
                asaas_subscription_id=subscription_id, is_active=True
            )
            .select_related("order", "client")
            .first()
        )
        if plan is not None:
            return plan

        checkout_session = str(subscription.get("checkoutSession") or "")
        if checkout_session:
            tx = Transaction.objects.filter(
                external_id=checkout_session, provider=self.name
            ).first()
            if tx is not None and tx.order_id is not None:
                plan = (
                    MaintenancePlan.objects.filter(order=tx.order, is_active=True)
                    .select_related("order", "client")
                    .first()
                )
        if plan is not None and not plan.asaas_subscription_id:
            plan.asaas_subscription_id = subscription_id
            plan.save(update_fields=["asaas_subscription_id", "updated_at"])
            logger.info(
                "Asaas: assinatura %s vinculada ao plano %s via webhook",
                subscription_id, plan.pk,
            )
        return plan

    def webhook(self, payload, headers) -> ChargeResult:
        """Processa webhook Asaas: autentica token e atualiza status."""
        from apps.payments.models import Transaction

        if isinstance(payload, bytes | bytearray):
            try:
                payload_str = payload.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("Payload deve estar em UTF-8.") from exc
        else:
            payload_str = payload or ""

        try:
            data = json.loads(payload_str or "{}")
        except (ValueError, TypeError) as exc:
            raise ValueError("Payload inválido: não é JSON válido.") from exc

        token = str(headers.get("asaas-access-token") or headers.get("x-webhook-token") or "")
        expected = getattr(settings, "ASAAS_WEBHOOK_TOKEN", "")
        if not expected or token != expected:
            raise WebhookAuthError("Assinatura de webhook Asaas inválida.")

        checkout = data.get("checkout") if isinstance(data, dict) else None
        if isinstance(checkout, dict) and checkout.get("id"):
            return self._handle_checkout_webhook(data, checkout, payload_str)

        event = str(data.get("event") or "").lower()
        subscription = data.get("subscription") if isinstance(data, dict) else None
        if isinstance(subscription, dict) and subscription.get("id") and event.startswith("subscription_"):
            return self._handle_subscription_webhook(data, subscription, event, payload_str)

        payment = data.get("payment") if isinstance(data, dict) else None
        if not isinstance(payment, dict) or not payment.get("id"):
            raise ValueError("Payload deve conter 'payment.id'.")

        external_id = str(payment.get("id"))
        tx = Transaction.objects.filter(external_id=external_id).first()

        if event == "payment_created":
            # Cobrança criada (ex.: nova fatura da assinatura). Abre a transação
            # pendente quando ainda não existe; nenhum ajuste de status além disso.
            if tx is None:
                tx = (
                    self._create_subscription_transaction(payment, external_id)
                    or self._create_payment_link_transaction(payment, external_id)
                    or self._resolve_checkout_payment_transaction(payment)
                )
                if tx is None:
                    # Cobrança desconhecida (ex.: checkout DETACHED sem vínculo
                    # local, evento de teste). Não interrompe a fila do Asaas.
                    logger.info(
                        "Asaas webhook: PAYMENT_CREATED %s sem transação local; ignorado.",
                        external_id,
                    )
                    return ChargeResult(
                        ok=True,
                        redirect_url="/",
                        message=f"Cobrança {external_id} sem transação local; ignorada.",
                        status=None,
                        raw_payload=payload_str,
                    )
                logger.info("Asaas webhook: transação criada %s", external_id)
                return ChargeResult(
                    ok=True,
                    redirect_url="/",
                    transaction_id=str(tx.pk),
                    message="Transação aguardando pagamento.",
                    status=tx.status,
                    raw_payload=payload_str,
                )
            return ChargeResult(
                ok=True,
                redirect_url="/",
                transaction_id=str(tx.pk),
                message="Transação aguardando pagamento.",
                status=tx.status,
                raw_payload=payload_str,
            )

        if tx is None:
            # Renovação de assinatura, paymentLink avulso ou pagamento redundante
            # de checkout: cobrança nova com id desconhecido, mas vinculada a uma
            # assinatura/solicitação/pedido registrado. Abre a transação antes de
            # aplicar o status do evento financeiro.
            tx = (
                self._create_subscription_transaction(payment, external_id)
                or self._create_payment_link_transaction(payment, external_id)
                or self._resolve_checkout_payment_transaction(payment)
            )
            if tx is None:
                # Evento financeiro sem transação local (ex.: teste do dashboard,
                # pagamento de checkout sem rastreio). Responde 200 para não
                # interromper a fila do Asaas nem marcar a entrega como falha.
                logger.warning(
                    "Asaas webhook: evento '%s' (%s) sem transação local; ignorado.",
                    event, external_id,
                )
                return ChargeResult(
                    ok=True,
                    redirect_url="/",
                    message=f"Evento '{event}' sem transação local; ignorado.",
                    status=None,
                    raw_payload=payload_str,
                )
            logger.info("Asaas webhook: renovação rastreada %s", external_id)

        if event in self._INFORMATIONAL_EVENTS:
            tx.raw_payload = payload_str
            tx.save(update_fields=["raw_payload", "updated_at"])
            return ChargeResult(
                ok=True,
                redirect_url="/",
                transaction_id=str(tx.pk),
                message=f"Evento informativo '{event}' processado sem transição.",
                status=tx.status,
                raw_payload=payload_str,
            )

        if event in self._AUTHORIZED_EVENTS:
            new_status = Transaction.Status.AUTHORIZED
        elif event in self._PAID_EVENTS:
            new_status = Transaction.Status.PAID
        elif event in self._FAILED_EVENTS:
            new_status = Transaction.Status.FAILED
        elif event in self._REFUNDED_EVENTS:
            new_status = Transaction.Status.REFUNDED
        else:
            # Eventos novos/desconhecidos não devem interromper a fila do Asaas:
            # registra o payload e responde 200 sem transição de status.
            logger.info("Asaas webhook: evento '%s' ignorado (sem transição).", event)
            tx.raw_payload = payload_str
            tx.save(update_fields=["raw_payload", "updated_at"])
            return ChargeResult(
                ok=True,
                redirect_url="/",
                transaction_id=str(tx.pk),
                message=f"Evento '{event}' ignorado.",
                status=tx.status,
                raw_payload=payload_str,
            )

        if tx.status != new_status:
            if not can_transition(tx.status, new_status):
                # Evento financeiro que tentaria reverter uma transação terminal
                # (ex.: payment_confirmed depois de já REFUNDED). Ignora sem
                # transição, mas registra o payload para auditoria.
                logger.info(
                    "Asaas webhook: transição %s -> %s bloqueada (%s)",
                    tx.status, new_status, external_id,
                )
                tx.raw_payload = payload_str
                tx.save(update_fields=["raw_payload", "updated_at"])
                return ChargeResult(
                    ok=True,
                    redirect_url="/",
                    transaction_id=str(tx.pk),
                    message=f"Transação '{tx.status} -> {new_status}' bloqueada.",
                    status=tx.status,
                    raw_payload=payload_str,
                )
            previous = tx.status
            tx.status = new_status
            tx.raw_payload = payload_str
            tx.save(update_fields=["status", "raw_payload", "updated_at"])
            logger.info("Asaas webhook: %s -> %s (%s)", previous, new_status, external_id)
        return ChargeResult(
            ok=True,
            redirect_url="/",
            transaction_id=str(tx.pk),
            message=f"Transação atualizada para {tx.status}.",
            status=tx.status,
            raw_payload=payload_str,
        )
