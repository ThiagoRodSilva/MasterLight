"""Views payments (webhook generico e confirmacao Pix)."""

import json
import logging

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.management import call_command
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from ..checkout.models import Order
from .services import WebhookAuthError, webhook_handler

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class WebhookView(View):
    """Endpoint generico webhook. provider decide como validar payload."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest) -> HttpResponse:
        try:
            webhook_handler(request.body, request.headers)
        except WebhookAuthError as exc:
            logger.warning("webhook nao autenticado: %s", exc)
            return HttpResponse(status=401)
        except ValueError as exc:
            message = str(exc)
            logger.warning("webhook invalido: %s", exc)
            if "não encontrada" in message:
                return HttpResponse(status=404)
            return HttpResponse(status=400)
        except Exception:
            logger.exception("erro inesperado no webhook")
            return HttpResponse(status=500)
        return HttpResponse(status=200)


class ReconcilePaymentsView(View):
    """Executa a reconciliacao de transacoes Asaas via Vercel Cron.

    Autenticado pelo header `Authorization: Bearer <CRON_SECRET>` que a Vercel
    injeta em /pagamentos/reconciliar quando a env CRON_SECRET esta definida.
    """

    http_method_names = ["post"]

    def post(self, request: HttpRequest) -> HttpResponse:
        secret = settings.CRON_SECRET
        auth = request.headers.get("Authorization", "")
        if not secret or auth != f"Bearer {secret}":
            return HttpResponse(status=403)
        try:
            call_command("sync_payments")
        except Exception:
            logger.exception("falha na reconciliacao via cron")
            return HttpResponse(status=500)
        return HttpResponse(status=200)


class PixConfirmationView(LoginRequiredMixin, TemplateView):
    """Mostra QR Code/copia-e-cola do Pix gerado no Asaas."""

    template_name = "payments/pix_confirm.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        order = get_object_or_404(Order, pk=self.kwargs["order_pk"], user=self.request.user)
        tx = order.transactions.filter(provider="asaas").order_by("-created_at").first()
        pix = {}
        if tx and tx.raw_payload:
            try:
                payload = json.loads(tx.raw_payload)
                pix = payload.get("pix") or {}
            except (ValueError, TypeError):
                pix = {}
        ctx["order"] = order
        ctx["transaction"] = tx
        ctx["pix"] = pix
        return ctx


class CardConfirmationView(LoginRequiredMixin, TemplateView):
    """Confirmação de pagamento com cartão de crédito (Asaas)."""

    template_name = "payments/card_confirm.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["order"] = get_object_or_404(Order, pk=self.kwargs["order_pk"], user=self.request.user)
        return ctx


class BoletoConfirmationView(LoginRequiredMixin, TemplateView):
    """Mostra o boleto bancário gerado no Asaas (link/linha digitável)."""

    template_name = "payments/boleto_confirm.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        order = get_object_or_404(Order, pk=self.kwargs["order_pk"], user=self.request.user)
        tx = order.transactions.filter(provider="asaas").order_by("-created_at").first()
        bank_slip = {}
        if tx and tx.raw_payload:
            try:
                payload = json.loads(tx.raw_payload)
                bank_slip = payload.get("bankSlip") or {}
            except (ValueError, TypeError):
                bank_slip = {}
        ctx["order"] = order
        ctx["transaction"] = tx
        ctx["bank_slip"] = bank_slip
        return ctx


class OrderStatusView(LoginRequiredMixin, View):
    """Retorna o status do pedido em JSON (usado pelo polling das telas).

    O usuário acessa apenas pedidos próprios; `paid` indica pagamento
    confirmado para o frontend trocar a seção por uma de sucesso.
    """

    def get(self, request, order_pk):
        order = get_object_or_404(Order, pk=order_pk, user=self.request.user)
        return JsonResponse(
            {
                "order_status": order.status,
                "paid": order.status == Order.Status.PAID,
                "canceled": order.status == Order.Status.CANCELED,
            }
        )


class ManualConfirmationView(LoginRequiredMixin, TemplateView):
    """Confirmação de pagamento manual (gateway `manual`)."""

    template_name = "payments/manual_confirm.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["order"] = get_object_or_404(Order, pk=self.kwargs["order_pk"], user=self.request.user)
        return ctx


class CheckoutCallbackView(LoginRequiredMixin, TemplateView):
    """Retorno do Asaas Checkout (successUrl/cancelUrl/expiredUrl).

    A confirmação financeira vem via webhook `CHECKOUT_PAID`; esta página apenas
    informa o usuário e aponta para o status do pedido (polling).
    """

    template_name = "payments/checkout_callback.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["order"] = get_object_or_404(Order, pk=self.kwargs["order_pk"], user=self.request.user)
        ctx["outcome"] = self.kwargs.get("outcome", "success")
        return ctx
