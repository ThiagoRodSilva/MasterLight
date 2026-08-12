"""Views de servicos: catalogo, solicitacoes e painel prestador."""

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.core.mixins import (
    ClienteRequiredMixin,
    OwnerRequiredMixin,
    ProviderRequiredMixin,
    SectionEnabledMixin,
)

from .forms import MaintenancePlanForm, ServiceForm, ServiceRequestForm
from .models import MaintenancePlan, MaintenanceVisit, Service, ServiceCategory, ServiceRequest


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
        if not self.request.user.is_admin:
            qs = qs.filter(service__providers=self.request.user) | qs.filter(
                service__created_by=self.request.user
            )
        return qs.select_related("service", "cliente", "prestador").order_by("-created_at")


class ServiceQuoteView(ProviderRequiredMixin, UpdateView):
    model = ServiceRequest
    fields = ["final_price"]
    template_name = "services/quote_form.html"
    context_object_name = "service_request"

    def get_queryset(self):
        qs = ServiceRequest.objects.filter(status="pending")
        if not self.request.user.is_admin:
            qs = qs.filter(service__providers=self.request.user) | qs.filter(
                service__created_by=self.request.user
            )
        return qs

    def form_valid(self, form):
        form.instance.status = ServiceRequest.Status.QUOTED
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, "Orçamento enviado ao cliente.")
        return reverse_lazy("services-provider-requests")


class ServiceRequestApproveView(ClienteRequiredMixin, View):
    """Permite ao cliente aprovar o orçamento escolhendo a forma de pagamento."""

    template_name = "services/request_approve.html"

    def get_queryset(self):
        return ServiceRequest.objects.filter(cliente=self.request.user, status="quoted")

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def get(self, request, *args, **kwargs):
        service_request = self.get_object()
        return render(request, self.template_name, {"service_request": service_request})

    def post(self, request, *args, **kwargs):
        from apps.checkout.models import Order, OrderItem
        from apps.payments.services import charge_with_rollback

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

            result = charge_with_rollback(
                order, request, fail_message="Falha ao gerar cobrança."
            )

        if result is None:
            return redirect("services-my-requests")
        return redirect(result.redirect_url)


class ServiceRequestPayLinkView(ClienteRequiredMixin, View):
    """Gera um link de pagamento avulso no Asaas para um orçamento.

    Retorna a URL da tela hospedada do Asaas em JSON; o frontend abre essa
    URL em uma nova aba. Não cria Order/Transaction (cobrança avulsa).
    """

    def get_queryset(self):
        return ServiceRequest.objects.filter(cliente=self.request.user, status="quoted")

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def post(self, request, *args, **kwargs):
        from apps.payments.services import create_payment_link

        service_request = self.get_object()
        try:
            result = create_payment_link(
                name=f"Orçamento — {service_request.service.name}",
                description=(
                    f"Orçamento de {service_request.service.name} "
                    f"(solicitação {service_request.pk})"
                ),
                value=service_request.final_price or service_request.service.base_price,
                billing_type="UNDEFINED",
                charge_type="DETACHED",
                external_reference=str(service_request.pk),
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc) or "Falha ao gerar link."}, status=400)
        return JsonResponse({"url": result.url, "link_id": result.link_id})


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


# --------------------------------------------------------------------------
# Manutenção elétrica (planos recorrentes)


class MaintenancePlanListView(SectionEnabledMixin, TemplateView):
    section_flag = "maintenance_enabled"
    template_name = "services/plan_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        prices = settings.MAINTENANCE_PLAN_PRICES
        ctx["plans"] = [
            {
                "value": t.value,
                "label": t.label,
                "price": prices.get(t.value, 0),
                "description": MaintenancePlan.DESCRIPTIONS[t.value],
            }
            for t in MaintenancePlan.PlanType
        ]
        return ctx


class MaintenancePlanCreateView(SectionEnabledMixin, ClienteRequiredMixin, FormView):
    section_flag = "maintenance_enabled"
    template_name = "services/plan_form.html"
    form_class = MaintenancePlanForm
    plan_type_label = {
        MaintenancePlan.PlanType.MONTHLY: _("Manutenção mensal"),
        MaintenancePlan.PlanType.QUARTERLY: _("Manutenção trimestral"),
        MaintenancePlan.PlanType.ANNUAL: _("Manutenção anual"),
    }

    def get_initial(self):
        initial = super().get_initial()
        tipo = self.request.GET.get("tipo")
        valid = {t.value for t in MaintenancePlan.PlanType}
        if tipo in valid:
            initial["plan_type"] = tipo
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["prices"] = settings.MAINTENANCE_PLAN_PRICES
        return ctx

    def form_valid(self, form):
        from apps.checkout.models import Order, OrderItem
        from apps.payments.services import resolve_billing, subscribe_plan

        value = form.cleaned_data["value"]
        plan_type = form.cleaned_data["plan_type"]
        prestador = form.cleaned_data["prestador"]
        next_due = timezone.localdate() + timedelta(days=MaintenancePlan.cycle_days_for(plan_type))

        try:
            params = resolve_billing(self.request, self.request.user)
            with transaction.atomic():
                order = Order.objects.create(
                    user=self.request.user,
                    status=Order.Status.AWAITING_PAYMENT,
                    kind=Order.Kind.SUBSCRIPTION,
                )
                OrderItem.objects.create(
                    order=order,
                    name=self.plan_type_label[plan_type],
                    qty=1,
                    unit_price=value,
                )
                order.recompute_total()
                plan = MaintenancePlan.objects.create(
                    plan_type=plan_type,
                    value=value,
                    next_due_date=next_due,
                    client=self.request.user,
                    prestador=prestador,
                    order=order,
                )
                result = subscribe_plan(
                    plan,
                    billing_type=params.billing_type,
                    credit_card_token=params.credit_card_token,
                    remote_ip=params.remote_ip,
                )
        except ValueError as exc:
            messages.error(self.request, str(exc) or "Falha ao criar a assinatura.")
            return redirect("services-plan-list")
        if result.ok:
            messages.success(self.request, "Assinatura criada. Aguardando o primeiro pagamento.")
            return redirect(result.redirect_url)
        order.status = Order.Status.CANCELED
        order.save(update_fields=["status", "updated_at"])
        plan.is_active = False
        plan.save(update_fields=["is_active", "updated_at"])
        messages.error(self.request, result.message or "Falha ao criar a assinatura.")
        return redirect("services-plan-list")


# --------------------------------------------------------------------------
# Prestador: visitas de manutenção


class MaintenanceVisitListView(ProviderRequiredMixin, ListView):
    template_name = "services/visits.html"
    context_object_name = "visits"
    paginate_by = 20

    def get_queryset(self):
        qs = MaintenanceVisit.objects.filter(completed_at__isnull=True)
        if not self.request.user.is_admin:
            qs = qs.filter(plan__prestador=self.request.user)
        return qs.select_related("plan", "plan__client", "plan__prestador")


class MaintenanceVisitCompleteView(ProviderRequiredMixin, UpdateView):
    model = MaintenanceVisit
    fields: list = []

    def get_queryset(self):
        qs = MaintenanceVisit.objects.filter(pk=self.kwargs["pk"])
        if not self.request.user.is_admin:
            qs = qs.filter(plan__prestador=self.request.user)
        return qs

    def post(self, request, *args, **kwargs):
        visit = self.get_object()
        visit.completed_at = timezone.now()
        visit.save(update_fields=["completed_at", "updated_at"])
        messages.success(request, "Visita concluída.")
        return redirect("services-visits")
