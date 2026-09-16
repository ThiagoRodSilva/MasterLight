"""Views de servicos: catalogo, solicitacoes e painel prestador."""

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from apps.checkout.models import Order
from apps.core.mixins import (
    ClienteRequiredMixin,
    OwnerRequiredMixin,
    ProviderRequiredMixin,
    SectionEnabledMixin,
)

from .forms import QuoteForm, ServiceForm, ServiceRequestForm
from .models import (
    Service,
    ServiceCategory,
    ServiceRequest,
)


class ServiceListView(SectionEnabledMixin, ListView):
    section_flag = "services_enabled"
    template_name = "services/list.html"
    context_object_name = "services"
    paginate_by = 12

    def get_queryset(self):
        qs = Service.objects.filter(is_active=True)
        cat = self.request.GET.get("categoria")
        if cat:
            qs = qs.filter(category__slug=cat)
        return qs.select_related("category").prefetch_related("providers")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = ServiceCategory.objects.filter(is_active=True)
        return ctx


class ServiceDetailView(SectionEnabledMixin, DetailView):
    section_flag = "services_enabled"
    template_name = "services/detail.html"
    context_object_name = "service"

    def get_queryset(self):
        return (
            Service.objects.filter(is_active=True)
            .select_related("category", "created_by")
            .prefetch_related("providers")
        )


# ---- Prestador self-service (CRUD de serviços) ------------------------------


class ServiceCreateView(ProviderRequiredMixin, CreateView):
    model = Service
    form_class = ServiceForm
    template_name = "services/service_form.html"
    success_url = reverse_lazy("services-my")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        # prestador que cria vira provider do proprio servico
        self.object.providers.add(self.request.user)
        messages.success(self.request, "Serviço criado e vinculado a você.")
        return response


class ServiceUpdateView(ProviderRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Service
    form_class = ServiceForm
    template_name = "services/service_form.html"
    context_object_name = "service"

    def get_success_url(self):
        messages.success(self.request, "Serviço atualizado.")
        return reverse_lazy("services-my")


class ServiceDeleteView(ProviderRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = Service
    template_name = "services/service_confirm_delete.html"
    context_object_name = "service"
    success_url = reverse_lazy("services-my")

    def form_valid(self, form):
        service = self.get_object()
        service.is_active = False
        service.save(update_fields=["is_active", "updated_at"])
        messages.success(self.request, "Serviço removido do catálogo.")
        return redirect("services-my")


class ServiceListViewMine(ProviderRequiredMixin, ListView):
    template_name = "services/my_services.html"
    context_object_name = "services"

    def get_queryset(self):
        return (
            Service.objects.filter(created_by=self.request.user, is_active=True)
            .select_related("category", "created_by")
            .prefetch_related("providers")
        )


# -------------------------------------------------------------------------


class ServiceRequestCreateView(SectionEnabledMixin, ClienteRequiredMixin, CreateView):
    section_flag = "services_enabled"
    model = ServiceRequest
    form_class = ServiceRequestForm
    template_name = "services/request_form.html"

    def get_service(self):
        return get_object_or_404(Service, slug=self.kwargs["slug"], is_active=True)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["service"] = self.get_service()
        return kwargs

    def form_valid(self, form):
        form.instance.cliente = self.request.user
        form.instance.service = self.get_service()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["service"] = self.get_service()
        return ctx

    def get_success_url(self):
        messages.success(self.request, "Solicitação enviada.")
        return reverse_lazy("services-my-requests")


# --------------------------------------------------------------------------
# Painel prestador: solicitações recebidas


class ProviderServiceRequestListView(ProviderRequiredMixin, ListView):
    template_name = "services/provider_requests.html"
    context_object_name = "requests"
    paginate_by = 20

    def get_queryset(self):
        qs = ServiceRequest.objects.filter(is_active=True)
        if not self.request.user.is_admin:
            qs = qs.filter(service__providers=self.request.user) | qs.filter(
                service__created_by=self.request.user
            )
        return qs.select_related("service", "cliente", "prestador").order_by("-created_at")


class ServiceQuoteView(ProviderRequiredMixin, UpdateView):
    model = ServiceRequest
    form_class = QuoteForm
    template_name = "services/quote_form.html"
    context_object_name = "service_request"

    def get_queryset(self):
        qs = ServiceRequest.objects.filter(is_active=True, status=ServiceRequest.Status.PENDING)
        if not self.request.user.is_admin:
            qs = qs.filter(service__providers=self.request.user) | qs.filter(
                service__created_by=self.request.user
            )
        return qs.select_related("service", "cliente", "prestador")

    def form_valid(self, form):
        form.instance.status = ServiceRequest.Status.QUOTED
        if form.instance.prestador_id is None:
            form.instance.prestador = self.request.user
        if form.instance.final_price is None:
            form.instance.final_price = form.instance.service.base_price
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, "Orçamento enviado ao cliente.")
        return reverse_lazy("services-provider-requests")


class ServiceRequestApproveView(ClienteRequiredMixin, View):
    """Permite ao cliente aprovar o orçamento escolhendo a forma de pagamento."""

    template_name = "services/request_approve.html"

    def get_queryset(self):
        return ServiceRequest.objects.filter(
            cliente=self.request.user, status=ServiceRequest.Status.QUOTED, is_active=True
        )

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def get(self, request, *args, **kwargs):
        service_request = self.get_object()
        # Asaas é o único provider — o link avulso está sempre disponível.
        return render(
            request,
            self.template_name,
            {"service_request": service_request, "PAYLINK_ENABLED": True},
        )

    def post(self, request, *args, **kwargs):
        from apps.checkout.models import Order, OrderItem
        from apps.payments.services import checkout_or_charge

        service_request = get_object_or_404(
            ServiceRequest.objects.select_for_update(),
            pk=self.kwargs["pk"],
            cliente=request.user,
            status=ServiceRequest.Status.QUOTED,
            is_active=True,
        )

        if service_request.order_id is not None:
            messages.error(request, "Esta solicitação já possui um pedido de pagamento associado.")
            return redirect("services-my-requests")

        with transaction.atomic():
            if service_request.status != ServiceRequest.Status.QUOTED:
                messages.error(request, "Solicitação não está aguardando aprovação.")
                return redirect("services-my-requests")

            order = Order.objects.create(
                user=request.user,
                status=Order.Status.AWAITING_PAYMENT,
                kind=Order.Kind.SERVICE,
            )
            final_price = (
                service_request.final_price
                if service_request.final_price is not None
                else service_request.service.base_price
            )
            OrderItem.objects.create(
                order=order,
                service=service_request.service,
                name=service_request.service.name,
                qty=1,
                unit_price=final_price,
            )
            order.recompute_total()
            from apps.affiliate.services import create_referral

            ref_code = request.COOKIES.get(settings.AFFILIATE_COOKIE_NAME)
            if ref_code:
                create_referral(ref_code, request.user, order)
            service_request.order = order
            service_request.save(update_fields=["order", "updated_at"])

            result = checkout_or_charge(order, request, fail_message="Falha ao gerar cobrança.")

        if result is None:
            order.status = Order.Status.CANCELED
            order.save(update_fields=["status", "updated_at"])
            service_request.order = None
            service_request.save(update_fields=["order", "updated_at"])
            return redirect("services-my-requests")
        if "url" in result:
            return redirect(result["url"])
        return redirect(result["redirect_url"])


class ServiceRequestPayLinkView(ClienteRequiredMixin, View):
    """Gera um link de pagamento avulso no Asaas para um orçamento.

    Retorna a URL da tela hospedada do Asaas em JSON; o frontend abre essa
    URL em uma nova aba. Não cria Order/Transaction (cobrança avulsa).
    """

    def get_queryset(self):
        return ServiceRequest.objects.filter(
            cliente=self.request.user, status=ServiceRequest.Status.QUOTED, is_active=True
        )

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def post(self, request, *args, **kwargs):
        from django.conf import settings

        from apps.payments.services import create_payment_link

        service_request = self.get_object()
        ref_code = request.COOKIES.get(settings.AFFILIATE_COOKIE_NAME)
        if ref_code:
            service_request.affiliate_ref_code = ref_code
            service_request.save(update_fields=["affiliate_ref_code", "updated_at"])
        final_price = (
            service_request.final_price
            if service_request.final_price is not None
            else service_request.service.base_price
        )
        try:
            result = create_payment_link(
                name=f"Orçamento — {service_request.service.name}",
                description=(
                    f"Orçamento de {service_request.service.name} "
                    f"(solicitação {service_request.pk})"
                ),
                value=final_price,
                billing_type="UNDEFINED",
                charge_type="DETACHED",
                external_reference=str(service_request.pk),
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc) or "Falha ao gerar link."}, status=400)
        if result.link_id:
            service_request.asaas_payment_link_id = result.link_id
            service_request.save(update_fields=["asaas_payment_link_id", "updated_at"])
        return JsonResponse({"url": result.url, "link_id": result.link_id})


class ServiceRequestCancelView(ClienteRequiredMixin, View):
    def get_queryset(self):
        return ServiceRequest.objects.filter(
            cliente=self.request.user,
            status__in=[ServiceRequest.Status.PENDING, ServiceRequest.Status.QUOTED],
            is_active=True,
        )

    def post(self, request, *args, **kwargs):
        service_request = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        service_request.status = ServiceRequest.Status.CANCELED
        service_request.save(update_fields=["status", "updated_at"])

        order = service_request.order
        if order and order.status in (Order.Status.OPEN, Order.Status.AWAITING_PAYMENT):
            order.status = Order.Status.CANCELED
            order.save(update_fields=["status", "updated_at"])

        messages.info(request, "Solicitação cancelada.")
        return redirect("services-my-requests")

    def get(self, request, *args, **kwargs):
        return redirect("services-my-requests")


# --------------------------------------------------------------------------
# Cliente: minhas solicitações


class MyServiceRequestListView(ClienteRequiredMixin, ListView):
    template_name = "services/my_requests.html"
    context_object_name = "requests"
    paginate_by = 20

    def get_queryset(self):
        return (
            ServiceRequest.objects.filter(cliente=self.request.user, is_active=True)
            .select_related("service", "prestador")
            .order_by("-created_at")
        )
