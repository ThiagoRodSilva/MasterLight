"""Views de servicos: catalogo, solicitacoes e painel prestador."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.mixins import (
    ClienteRequiredMixin,
    OwnerRequiredMixin,
    ProviderRequiredMixin,
    SectionEnabledMixin,
)

from .forms import ServiceForm, ServiceRequestForm
from .models import Service, ServiceCategory, ServiceRequest


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
        return qs.select_related("category")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = ServiceCategory.objects.filter(is_active=True)
        return ctx


class ServiceDetailView(SectionEnabledMixin, DetailView):
    section_flag = "services_enabled"
    template_name = "services/detail.html"
    context_object_name = "service"

    def get_queryset(self):
        return Service.objects.filter(is_active=True).select_related("category")


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


class ServiceUpdateView(OwnerRequiredMixin, UpdateView):
    model = Service
    form_class = ServiceForm
    template_name = "services/service_form.html"
    context_object_name = "service"

    def get_queryset(self):
        return super().get_queryset().filter(created_by=self.request.user)

    def get_success_url(self):
        messages.success(self.request, "Serviço atualizado.")
        return reverse_lazy("services-my")


class ServiceDeleteView(OwnerRequiredMixin, DeleteView):
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
        return Service.objects.filter(created_by=self.request.user).select_related("category")


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
        qs = ServiceRequest.objects.all()
        if not self.request.user.role == "admin":
            qs = qs.filter(service__created_by=self.request.user)
        return qs.select_related("service", "cliente", "prestador").order_by("-created_at")


class ServiceQuoteView(ProviderRequiredMixin, UpdateView):
    model = ServiceRequest
    fields = ["final_price"]
    template_name = "services/quote_form.html"
    context_object_name = "service_request"

    def get_queryset(self):
        qs = ServiceRequest.objects.filter(status="pending")
        if not self.request.user.role == "admin":
            qs = qs.filter(service__created_by=self.request.user)
        return qs

    def form_valid(self, form):
        form.instance.status = ServiceRequest.Status.QUOTED
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, "Orçamento enviado ao cliente.")
        return reverse_lazy("services-provider-requests")


class ServiceRequestApproveView(ClienteRequiredMixin, UpdateView):
    model = ServiceRequest
    fields: list = []

    def get_queryset(self):
        return ServiceRequest.objects.filter(cliente=self.request.user, status="quoted")

    def post(self, request, *args, **kwargs):
        from apps.checkout.models import Order, OrderItem

        service_request = self.get_object()
        with transaction.atomic():
            if service_request.status != ServiceRequest.Status.QUOTED:
                messages.error(request, "Solicitação não está aguardando aprovação.")
                return redirect("services-my-requests")

            order = Order.objects.create(
                user=request.user,
                status=Order.Status.AWAITING_PAYMENT,
                kind=Order.Kind.SERVICE,
            )
            OrderItem.objects.create(
                order=order,
                service=service_request.service,
                name=service_request.service.name,
                qty=1,
                unit_price=service_request.final_price or service_request.service.base_price,
            )
            order.recompute_total()
            service_request.order = order
            service_request.save(update_fields=["order", "updated_at"])

            from apps.payments.services import charge_order

            result = charge_order(order, billing_type="PIX")

            if result.ok:
                return redirect(result.redirect_url)
            order.status = Order.Status.CANCELED
            order.save(update_fields=["status", "updated_at"])
            messages.error(request, result.message or "Falha ao gerar cobrança.")
            return redirect("services-my-requests")


class ServiceRequestCancelView(ClienteRequiredMixin, UpdateView):
    model = ServiceRequest

    def get_queryset(self):
        return ServiceRequest.objects.filter(
            cliente=self.request.user, status__in=["pending", "quoted"]
        )

    def post(self, request, *args, **kwargs):
        service_request = self.get_object()
        service_request.status = ServiceRequest.Status.CANCELED
        service_request.save(update_fields=["status", "updated_at"])
        messages.info(request, "Solicitação cancelada.")
        return redirect("services-my-requests")


# --------------------------------------------------------------------------
# Cliente: minhas solicitações


class MyServiceRequestListView(LoginRequiredMixin, ListView):
    template_name = "services/my_requests.html"
    context_object_name = "requests"
    paginate_by = 20

    def get_queryset(self):
        return (
            ServiceRequest.objects.filter(cliente=self.request.user)
            .select_related("service", "prestador")
            .order_by("-created_at")
        )
