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


class PaymentGateway:
    """Interface abstrata gateway pagamento.

    Cada provedor concreto (Asaas, Mercado Pago, Stripe, etc.) deve herdar
    desta classe e implementar `charge`, `refund` e `webhook`.
    """

    name: str = "base"

    def charge(self, order) -> ChargeResult:
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
            body["cpfCnpj"] = user.cpf
        customer = self._api("POST", "customers", body)
        customer_id = customer["id"]
        user.asaas_customer_id = customer_id
        user.save(update_fields=["asaas_customer_id"])
        return customer_id

    def _fetch_pix(self, payment_id: str) -> dict:
        return self._api("GET", f"payments/{payment_id}/pixQrCode")

    def charge(self, order, billing_type: str = "PIX") -> ChargeResult:
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
        # Cartao requer token client-side (creditCardToken). Sem token, o Asaas
        # retorna erro; mantemos payload simples e documentamos no README.
        if normalized == "CREDIT_CARD":
            body.setdefault("creditCard", {})

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
        redirect_url = str(reverse_lazy("payments-pix-confirm", kwargs={"order_pk": order.pk}))
        return ChargeResult(
            ok=True,
            redirect_url=redirect_url,
            external_id=str(tx.pk),
            message=f"Cobrança {normalized} criada para análise.",
            status=Transaction.Status.PENDING,
            raw_payload=json.dumps({"payment": payment, "pix": pix}),
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
        if expected and token != expected:
            raise WebhookAuthError("Assinatura de webhook Asaas inválida.")

        payment = data.get("payment") if isinstance(data, dict) else None
        if not isinstance(payment, dict) or not payment.get("id"):
            raise ValueError("Payload deve conter 'payment.id'.")

        external_id = str(payment.get("id"))
        event = str(data.get("event") or "").lower()
        tx = Transaction.objects.filter(external_id=external_id).first()
        if tx is None:
            raise ValueError("Transação não encontrada.")

        if event in ("payment_confirmed", "payment_received", "payment_authorized"):
            tx.status = Transaction.Status.PAID
        elif event in ("payment_overdue", "payment_deleted", "payment_failed"):
            tx.status = Transaction.Status.FAILED
        elif event in ("payment_refunded", "payment_refund_requested"):
            tx.status = Transaction.Status.REFUNDED
        else:
            raise ValueError(f"Evento de webhook '{event}' não mapeado.")

        tx.raw_payload = payload_str
        tx.save(update_fields=["status", "raw_payload", "updated_at"])
        return ChargeResult(
            ok=True,
            redirect_url="/",
            external_id=str(tx.pk),
            message=f"Transação atualizada para {tx.status}.",
            status=tx.status,
        )


_REGISTRY = {
    "manual": ManualGateway,
    "asaas": AsaasGateway,
}


def get_gateway() -> PaymentGateway:
    provider = getattr(settings, "PAYMENT_PROVIDER", "manual")
    cls = _REGISTRY.get(provider, ManualGateway)
    return cls()


def charge_order(order, billing_type: str = "PIX") -> ChargeResult:
    """Cria transacao inicial e chama gateway configurado."""
    from .models import Transaction

    gateway = get_gateway()
    if gateway.name == "asaas":
        result = gateway.charge(order, billing_type=billing_type)
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


def webhook_handler(payload, headers) -> dict:
    """Processa webhook generico e retorna dicionario serializavel."""
    result = get_gateway().webhook(payload, headers)
    return asdict(result)
