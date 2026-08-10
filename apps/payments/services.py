"""Servicos orquestracao pagamentos (camada de negocio)."""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Optional

import requests
from django.conf import settings
from django.urls import reverse_lazy


class WebhookAuthError(ValueError):
    """Erro de autenticação de webhook (token ausente/inválido)."""


@dataclass
class ChargeResult:
    ok: bool
    redirect_url: str
    external_id: str = ""
    message: str = ""
    raw_payload: str = ""
    status: Optional[str] = None
    subscription_id: str = ""


class PaymentGateway:
    """Interface abstrata gateway pagamento.

    Cada provedor concreto (Asaas, Mercado Pago, Stripe, etc.) deve herdar
    desta classe e implementar `charge`, `refund` e `webhook`.
    """

    name: str = "base"

    def charge(self, order) -> ChargeResult:
        raise NotImplementedError

    def subscribe(self, plan, billing_type: str = "PIX") -> ChargeResult:
        """Cria assinatura recorrente para um plano de manutenção."""
        raise NotImplementedError

    def tokenize_credit_card(self, user, card: dict, holder: dict, remote_ip: str = "") -> str:
        """Tokeniza cartão de crédito; apenas providers que suportam cartão."""
        raise NotImplementedError

    def refund(self, transaction_id, amount) -> ChargeResult:  # pragma: no cover
        raise NotImplementedError

    def webhook(self, payload, headers) -> ChargeResult:  # pragma: no cover
        raise NotImplementedError


class ManualGateway(PaymentGateway):
    """Gateway testes: marca transacao como pendente sem cobrar fato.

    webhook recebe payload JSON com `transaction_id` e `status` (paid/refunded)
    para simular confirmacao manual de pagamento.
    """

    name = "manual"

    def charge(self, order) -> ChargeResult:
        from .models import Transaction

        tx = Transaction.objects.create(
            order=order,
            user=order.user,
            provider=self.name,
            amount=order.total,
            status=Transaction.Status.PENDING,
        )
        return ChargeResult(
            ok=True,
            redirect_url=str(
                reverse_lazy("payments-manual-confirm", kwargs={"order_pk": order.pk})
            ),
            external_id=str(tx.pk),
            message="Pedido criado. Pagamento manual em análise.",
        )

    def subscribe(self, plan, billing_type: str = "PIX") -> ChargeResult:
        from .models import Transaction

        tx = Transaction.objects.create(
            order=plan.order,
            user=plan.client,
            provider=self.name,
            amount=plan.value,
            status=Transaction.Status.PENDING,
        )
        return ChargeResult(
            ok=True,
            redirect_url=str(
                reverse_lazy("payments-manual-confirm", kwargs={"order_pk": plan.order.pk})
            ),
            external_id=str(tx.pk),
            message="Assinatura criada. Pagamento manual em análise.",
        )

    def tokenize_credit_card(self, user, card: dict, holder: dict, remote_ip: str = "") -> str:
        raise ValueError("Cartão de crédito requer o provider 'asaas'.")

    def refund(self, transaction_id, amount) -> ChargeResult:
        from .models import Transaction

        tx = Transaction.objects.filter(pk=transaction_id).first()
        if tx:
            tx.status = Transaction.Status.REFUNDED
            tx.save(update_fields=["status", "updated_at"])
            return ChargeResult(ok=True, redirect_url="/", external_id=str(tx.pk))
        return ChargeResult(ok=False, redirect_url="/", message="Tx não encontrada.")

    def webhook(self, payload, headers) -> ChargeResult:
        from .models import Transaction

        token = str(headers.get("x-webhook-token") or "")
        if not settings.MANUAL_WEBHOOK_TOKEN:
            raise WebhookAuthError(
                "MANUAL_WEBHOOK_TOKEN não configurada (webhook manual desabilitado)."
            )
        if token != settings.MANUAL_WEBHOOK_TOKEN:
            raise WebhookAuthError("Assinatura de webhook manual inválida.")

        if isinstance(payload, (bytes, bytearray)):
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

        if not isinstance(data, dict):
            raise ValueError("Payload deve ser um objeto JSON.")

        transaction_id = data.get("transaction_id")
        status = (data.get("status") or "").lower()
        if not transaction_id or not status:
            raise ValueError("Payload deve conter 'transaction_id' e 'status'.")
        try:
            transaction_id = str(uuid.UUID(str(transaction_id)))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"transaction_id '{transaction_id}' não é um UUID válido.") from exc

        tx = Transaction.objects.filter(pk=transaction_id).first()
        if tx is None:
            raise ValueError(f"Transação {transaction_id} não encontrada.")

        try:
            tx.status = Transaction.Status(status)
        except ValueError as exc:
            raise ValueError(f"Status '{status}' inválido.") from exc

        tx.raw_payload = payload_str
        tx.save(update_fields=["status", "raw_payload", "updated_at"])

        return ChargeResult(
            ok=True,
            redirect_url="/",
            external_id=str(tx.pk),
            message=f"Transação atualizada para {tx.status}.",
            status=tx.status,
            raw_payload=payload_str,
        )


class AsaasGateway(PaymentGateway):
    """Gateway real via API v3 do Asaas (Pix e MultiCartão).

    - `charge` cria cobrança e salva `Transaction.external_id` = id Asaas.
    - `webhook` valida token em `x-webhook-token` e mapeia eventos
      PAYMENT_CONFIRMED/RECEIVED -> paid, PAYMENT_OVERDUE/RESET -> failed.
    - Ambiente sandbox/prod controlado por `ASAAS_SANDBOX`.
    """

    name = "asaas"
    base_url_sandbox = "https://sandbox.asaas.com/api/v3"
    base_url_prod = "https://api.asaas.com/api/v3"
    timeout = 15

    @property
    def api_base_url(self) -> str:
        return self.base_url_prod if not settings.ASAAS_SANDBOX else self.base_url_sandbox

    def _headers(self) -> dict:
        return {
            "access_token": settings.ASAAS_API_KEY,
            "Content-Type": "application/json",
        }

    def _api(self, method: str, path: str, payload=None) -> dict:
        """Chama a API do Asaas. Levanta ValueError em qualquer erro de HTTP."""
        if not settings.ASAAS_API_KEY:
            raise ValueError("ASAAS_API_KEY não configurada.")
        url = f"{self.api_base_url}/{path.lstrip('/')}"
        response = requests.request(
            method, url, headers=self._headers(), json=payload, timeout=self.timeout
        )
        if not response.ok:
            try:
                detail = response.json()
            except (ValueError, TypeError):
                detail = response.text[:200]
            raise ValueError(f"Erro Asaas {response.status_code}: {detail}")
        return response.json()

    def _sanitize_digits(self, value: str) -> str:
        """Remove máscara de CPF/CNPJ, mantendo apenas dígitos."""
        return "".join(ch for ch in (value or "") if ch.isdigit())

    def _ensure_customer(self, user) -> str:
        """Reutiliza (e salva) o customer_id do Asaas no usuario."""
        if getattr(user, "asaas_customer_id", ""):
            return user.asaas_customer_id
        full_name = user.get_full_name() or user.username or user.email
        body = {
            "name": full_name,
            "email": user.email,
            "externalReference": str(user.pk),
        }
        if user.cpf:
            body["cpfCnpj"] = self._sanitize_digits(user.cpf)
        customer = self._api("POST", "customers", body)
        customer_id = customer["id"]
        user.asaas_customer_id = customer_id
        user.save(update_fields=["asaas_customer_id"])
        return customer_id

    def _fetch_pix(self, payment_id: str) -> dict:
        return self._api("GET", f"payments/{payment_id}/pixQrCode")

    def tokenize_credit_card(self, user, card: dict, holder: dict, remote_ip: str = "") -> str:
        """Gera `creditCardToken` no Asaas (tokenização de cartão).

        O token fica vinculado ao customer; cobranças seguintes do mesmo
        cliente podem reusá-lo sem trafegar dados do cartão novamente.
        """
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
                "phone": holder.get("phone", ""),
            },
            "remoteIp": remote_ip,
        }
        result = self._api("POST", "creditCards/tokenizeCreditCard", body)
        token = result.get("creditCardToken") or result.get("credit_card_token")
        if not token:
            raise ValueError("Falha ao tokenizar cartão: resposta sem creditCardToken.")
        return token

    def charge(self, order, billing_type: str = "PIX", credit_card_token: str = "", remote_ip: str = "") -> ChargeResult:
        """Gera cobranca Pix ou cartao no Asaas e salva Transaction."""
        from .models import Transaction

        normalized = (billing_type or "PIX").upper()
        if normalized not in ("PIX", "CREDIT_CARD"):
            raise ValueError(f"billing_type inválido: {billing_type} (use PIX ou CREDIT_CARD).")

        customer = self._ensure_customer(order.user)
        due_date = date.today() + timedelta(days=1)
        body = {
            "customer": customer,
            "billingType": normalized,
            "value": float(order.total),
            "dueDate": due_date.isoformat(),
        }
        if normalized == "CREDIT_CARD":
            if not credit_card_token:
                raise ValueError("CREDIT_CARD exige um creditCardToken (tokenize primeiro).")
            body["creditCardToken"] = credit_card_token
            if remote_ip:
                body["remoteIp"] = remote_ip

        payment = self._api("POST", "payments", body)
        pix = self._fetch_pix(payment["id"]) if normalized == "PIX" else {}

        tx = Transaction.objects.create(
            order=order,
            user=order.user,
            provider=self.name,
            external_id=payment["id"],
            amount=order.total,
            status=Transaction.Status.PENDING,
            raw_payload=json.dumps({"payment": payment, "pix": pix}),
        )
        if normalized == "CREDIT_CARD":
            redirect_url = str(reverse_lazy("payments-manual-confirm", kwargs={"order_pk": order.pk}))
        else:
            redirect_url = str(reverse_lazy("payments-pix-confirm", kwargs={"order_pk": order.pk}))
        return ChargeResult(
            ok=True,
            redirect_url=redirect_url,
            external_id=str(tx.pk),
            message=f"Cobrança {normalized} criada para análise.",
            status=Transaction.Status.PENDING,
            raw_payload=json.dumps({"payment": payment, "pix": pix}),
        )

    def subscribe(self, plan, billing_type: str = "PIX", credit_card_token: str = "", remote_ip: str = "") -> ChargeResult:
        """Cria assinatura recorrente no Asaas e mapeia a 1ª cobrança."""
        from .models import Transaction

        normalized = (billing_type or "PIX").upper()
        if normalized not in ("PIX", "CREDIT_CARD"):
            raise ValueError(f"billing_type inválido: {billing_type} (use PIX ou CREDIT_CARD).")

        cycle_map = {
            "mensal": "MONTHLY",
            "trimestral": "QUARTERLY",
            "anual": "YEARLY",
        }
        cycle = cycle_map.get(plan.plan_type, "MONTHLY")
        customer = self._ensure_customer(plan.client)
        body = {
            "customer": customer,
            "billingType": normalized,
            "value": float(plan.value),
            "nextDueDate": plan.next_due_date.isoformat(),
            "cycle": cycle,
        }
        if normalized == "CREDIT_CARD":
            if not credit_card_token:
                raise ValueError("CREDIT_CARD exige um creditCardToken (tokenize primeiro).")
            body["creditCardToken"] = credit_card_token
            if remote_ip:
                body["remoteIp"] = remote_ip
        subscription = self._api("POST", "subscriptions", body)
        subscription_id = subscription["id"]

        # Primeira cobranca da assinatura: usa o id do payment para que o
        # webhook existente (mapeado por Transaction.external_id) o encontre.
        external_payment_id = subscription_id
        try:
            payments = self._api("GET", f"subscriptions/{subscription_id}/payments")
        except ValueError:
            payments = {}
        rows = payments.get("data") if isinstance(payments, dict) else None
        if rows:
            first = rows[0]
            external_payment_id = first.get("id") or subscription_id

        try:
            pix = self._fetch_pix(external_payment_id) if normalized == "PIX" else {}
        except ValueError:
            # Cobrança ainda não possui Pix disponível (ex.: cartão sem emissão
            # imediata); segue sem QR, o status é atualizado via webhook.
            pix = {}

        tx = Transaction.objects.create(
            order=plan.order,
            user=plan.client,
            provider=self.name,
            external_id=external_payment_id,
            amount=plan.value,
            status=Transaction.Status.PENDING,
            raw_payload=json.dumps({"subscription": subscription, "first_payment": external_payment_id, "pix": pix}),
        )

        plan.asaas_subscription_id = subscription_id
        plan.save(update_fields=["asaas_subscription_id", "updated_at"])

        if normalized == "CREDIT_CARD":
            redirect_url = str(reverse_lazy("payments-manual-confirm", kwargs={"order_pk": plan.order.pk}))
        else:
            redirect_url = str(reverse_lazy("payments-pix-confirm", kwargs={"order_pk": plan.order.pk}))
        return ChargeResult(
            ok=True,
            redirect_url=redirect_url,
            external_id=str(tx.pk),
            message="Assinatura criada. Aguardando o primeiro pagamento.",
            status=Transaction.Status.PENDING,
            raw_payload=json.dumps({"subscription": subscription, "first_payment": external_payment_id, "pix": pix}),
            subscription_id=subscription_id,
        )

    def refund(self, transaction_id, amount) -> ChargeResult:
        from .models import Transaction

        tx = Transaction.objects.filter(pk=transaction_id).first()
        if tx is None or not tx.external_id:
            return ChargeResult(ok=False, redirect_url="/", message="Tx não encontrada.")
        try:
            self._api("POST", f"payments/{tx.external_id}/refund", {"value": float(amount)})
        except ValueError:
            return ChargeResult(ok=False, redirect_url="/", message="Falha no reembolso.")
        tx.status = Transaction.Status.REFUNDED
        tx.save(update_fields=["status", "updated_at"])
        return ChargeResult(
            ok=True,
            redirect_url="/",
            external_id=str(tx.pk),
message="Reembolso solicitado.",
        )

    def _create_subscription_transaction(self, payment, external_id):
        """Cria Transaction para uma cobrança de assinatura (renovação).

        Renovações chegam via webhook com um `payment.id` novo, ainda sem
        `Transaction` local. O payload traz `payment.subscription`; mapeamos
        para o `MaintenancePlan.asaas_subscription_id` e abrimos a transação
        pendente ligada ao pedido do plano. Retorna None se não encontrar plano.
        """
        from apps.services.models import MaintenancePlan

        from .models import Transaction

        subscription_id = payment.get("subscription") if isinstance(payment, dict) else None
        if not subscription_id:
            return None
        plan = (
            MaintenancePlan.objects.filter(
                asaas_subscription_id=str(subscription_id), is_active=True
            )
            .select_related("order", "client")
            .first()
        )
        if plan is None or plan.order is None:
            return None
        return Transaction.objects.create(
            order=plan.order,
            user=plan.client,
            provider=self.name,
            external_id=external_id,
            amount=payment.get("value") or plan.value,
            status=Transaction.Status.PENDING,
            raw_payload=json.dumps(payment),
        )

    def webhook(self, payload, headers) -> ChargeResult:
        """Processa webhook Asaas: autentica token e atualiza status."""
        from .models import Transaction

        if isinstance(payload, (bytes, bytearray)):
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

        token = str(headers.get("x-webhook-token") or "")
        expected = settings.ASAAS_WEBHOOK_TOKEN
        if not expected or token != expected:
            raise WebhookAuthError("Assinatura de webhook Asaas inválida.")

        payment = data.get("payment") if isinstance(data, dict) else None
        if not isinstance(payment, dict) or not payment.get("id"):
            raise ValueError("Payload deve conter 'payment.id'.")

        external_id = str(payment.get("id"))
        event = str(data.get("event") or "").lower()
        tx = Transaction.objects.filter(external_id=external_id).first()

        if event == "payment_created":
            # Cobrança criada (ex.: nova fatura da assinatura). Abre a transação
            # pendente quando ainda não existe; nenhum ajuste de status além disso.
            if tx is None:
                tx = self._create_subscription_transaction(payment, external_id)
                if tx is None:
                    raise ValueError("Transação não encontrada.")
                return ChargeResult(
                    ok=True,
                    redirect_url="/",
                    external_id=str(tx.pk),
                    message="Transação aguardando pagamento.",
                    status=tx.status,
                    raw_payload=payload_str,
                )
            return ChargeResult(
                ok=True,
                redirect_url="/",
                external_id=str(tx.pk),
                message="Transação aguardando pagamento.",
                status=tx.status,
                raw_payload=payload_str,
            )

        if tx is None:
            # Renovação de assinatura: cobrança nova com id desconhecido, mas
            # pertencente a uma assinatura registrada. Abre a transação antes de
            # aplicar o status do evento financeiro.
            tx = self._create_subscription_transaction(payment, external_id)
            if tx is None:
                raise ValueError("Transação não encontrada.")

        if event in ("payment_confirmed", "payment_received", "payment_authorized"):
            new_status = Transaction.Status.PAID
        elif event in ("payment_overdue", "payment_deleted", "payment_failed"):
            new_status = Transaction.Status.FAILED
        elif event in ("payment_refunded", "payment_refund_requested"):
            new_status = Transaction.Status.REFUNDED
        else:
            raise ValueError(f"Evento de webhook '{event}' não mapeado.")

        if tx.status != new_status:
            tx.status = new_status
            tx.raw_payload = payload_str
            tx.save(update_fields=["status", "raw_payload", "updated_at"])
        return ChargeResult(
            ok=True,
            redirect_url="/",
            external_id=str(tx.pk),
            message=f"Transação atualizada para {tx.status}.",
            status=tx.status,
            raw_payload=payload_str,
        )


_REGISTRY = {
    "manual": ManualGateway,
    "asaas": AsaasGateway,
}


def get_gateway() -> PaymentGateway:
    provider = getattr(settings, "PAYMENT_PROVIDER", "manual")
    cls = _REGISTRY.get(provider, ManualGateway)
    return cls()


def prepare_card_payload(post, user, address=None) -> tuple[dict, dict]:
    """Valida dados de cartão do POST e monta `card`/`holder` para tokenização.

    Levanta `ValueError` com mensagem amigável se faltar CPF/endereço do titular
    (o Asaas exige `cpfCnpj`, `postalCode` e `addressNumber`) ou se a validade
    estiver no passado. O CPF é sanitizado apenas com dígitos.
    """
    cpf = "".join(ch for ch in (post.get("card_cpf") or user.cpf or "") if ch.isdigit())
    if not cpf:
        raise ValueError("Informe o CPF do titular do cartão.")
    if address is None or not (address.zip_code or "").strip() or not (address.number or "").strip():
        raise ValueError("Cadastre um endereço com CEP e número para pagar com cartão.")

    try:
        month = int(post.get("card_expiry_month") or 0)
    except (TypeError, ValueError):
        month = 0
    try:
        year = int(post.get("card_expiry_year") or 0)
    except (TypeError, ValueError):
        year = 0
    if month < 1 or month > 12:
        raise ValueError("Mês de validade do cartão inválido.")
    from datetime import date

    if date(year, month, 1) <= date.today().replace(day=1):
        raise ValueError("Cartão de crédito vencido.")

    holder = {
        "name": user.get_full_name() or user.email,
        "email": user.email,
        "cpf_cnpj": cpf,
        "phone": user.telefone,
        "postal_code": address.zip_code,
        "address_number": address.number,
    }
    card = {
        "holder_name": post.get("card_holder", ""),
        "number": post.get("card_number", ""),
        "expiry_month": f"{month:02d}",
        "expiry_year": str(year),
        "ccv": post.get("card_ccv", ""),
    }
    return card, holder


def charge_order(order, billing_type: str = "PIX", credit_card_token: str = "", remote_ip: str = "") -> ChargeResult:
    """Cria transacao inicial e chama gateway configurado."""
    from .models import Transaction

    gateway = get_gateway()
    if gateway.name == "asaas":
        result = gateway.charge(
            order, billing_type=billing_type, credit_card_token=credit_card_token, remote_ip=remote_ip
        )
    else:
        result = gateway.charge(order)
    if result.external_id:
        tx = Transaction.objects.filter(pk=result.external_id).first()
        if tx:
            if not result.ok:
                tx.status = Transaction.Status.FAILED
            else:
                # Mantém o status informado pelo gateway (ex.: PENDING no Pix),
                # preservando a semântica: cobrança criada ≠ pagamento confirmado.
                tx.status = result.status or tx.status
            tx.raw_payload = result.raw_payload
            tx.save(update_fields=["status", "raw_payload", "updated_at"])
    return result


def subscribe_plan(plan, billing_type: str = "PIX", credit_card_token: str = "", remote_ip: str = "") -> ChargeResult:
    """Cria transacao de assinatura e chama gateway configurado."""
    gateway = get_gateway()
    if gateway.name == "asaas":
        result = gateway.subscribe(
            plan, billing_type=billing_type, credit_card_token=credit_card_token, remote_ip=remote_ip
        )
    else:
        result = gateway.subscribe(plan)
    return result


def webhook_handler(payload, headers) -> dict:
    """Processa webhook generico e retorna dicionario serializavel."""
    result = get_gateway().webhook(payload, headers)
    return asdict(result)
