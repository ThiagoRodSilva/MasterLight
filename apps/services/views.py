"""Views de servicos: catalogo, solicitacoes e painel prestador."""

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
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

from apps.checkout.models import Order
from apps.core.mixins import (
    ClienteRequiredMixin,
    OwnerRequiredMixin,
    ProviderRequiredMixin,
    SectionEnabledMixin,
)

from .forms import MaintenancePlanForm, QuoteForm, ServiceForm, ServiceRequestForm
from .models import (
    MaintenancePlan,
    MaintenancePlanTemplate,
    MaintenanceVisit,
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
        return Service.objects.filter(is_active=True).select_related("category", "created_by").prefetch_related("providers")


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
        return Service.objects.filter(created_by=self.request.user, is_active=True).select_related("category", "created_by").prefetch_related("providers")


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
        return render(request, self.template_name, {"service_request": service_request})

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
            from apps.affiliate.services import create_referral_from_request

            create_referral_from_request(request, order)
            service_request.order = order
            service_request.save(update_fields=["order", "updated_at"])

            result = checkout_or_charge(order, request, fail_message="Falha ao gerar cobrança.")

        if result is None:
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


# --------------------------------------------------------------------------
# Manutenção elétrica (planos recorrentes)


class MaintenancePlanListView(SectionEnabledMixin, TemplateView):
    section_flag = "maintenance_enabled"
    template_name = "services/plan_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["plans"] = MaintenancePlanTemplate.objects.filter(is_active=True).order_by(
            "ordering", "value"
        )
        return ctx


class MaintenancePlanCreateView(SectionEnabledMixin, ClienteRequiredMixin, FormView):
    section_flag = "maintenance_enabled"
    template_name = "services/plan_form.html"
    form_class = MaintenancePlanForm

    def get_initial(self):
        initial = super().get_initial()
        tipo = self.request.GET.get("tipo")
        if tipo and MaintenancePlanTemplate.objects.filter(
            plan_type=tipo, is_active=True
        ).exists():
            initial["plan_type"] = tipo
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["prices"] = {
            t.plan_type: t.value
            for t in MaintenancePlanTemplate.objects.filter(is_active=True)
        }
        return ctx

    def form_valid(self, form):
        from apps.checkout.models import Order, OrderItem
        from apps.payments.services import (
            create_checkout_for_order,
            resolve_billing,
            subscribe_plan,
        )

        value = form.cleaned_data["value"]
        plan_type = form.cleaned_data["plan_type"]
        prestador = form.cleaned_data["prestador"]
        template = MaintenancePlanTemplate.objects.get(
            plan_type=plan_type, is_active=True
        )
        next_due = timezone.localdate() + timedelta(days=MaintenancePlan.cycle_days_for(plan_type))

        existing_plan = MaintenancePlan.objects.filter(
            client=self.request.user,
            plan_type=plan_type,
            is_active=True,
        ).exclude(order__isnull=True).first()
        if existing_plan:
            messages.error(
                self.request,
                "Você já possui um plano ativo ou aguardando pagamento deste tipo.",
            )
            return redirect("services-plan-list")

        try:
            with transaction.atomic():
                order = Order.objects.create(
                    user=self.request.user,
                    status=Order.Status.AWAITING_PAYMENT,
                    kind=Order.Kind.SUBSCRIPTION,
                )
                OrderItem.objects.create(
                    order=order,
                    name=template.name,
                    qty=1,
                    unit_price=value,
                )
                order.recompute_total()
                from apps.affiliate.services import create_referral_from_request

                create_referral_from_request(self.request, order)
                plan = MaintenancePlan.objects.create(
                    plan_type=plan_type,
                    value=value,
                    next_due_date=next_due,
                    client=self.request.user,
                    prestador=prestador,
                    order=order,
                )
                if settings.PAYMENT_PROVIDER == "asaas":
                    result = create_checkout_for_order(
                        order,
                        self.request,
                        charge_type="RECURRENT",
                        cycle=plan_type,
                        next_due_date=next_due,
                    )
                    redirect_url = result.url
                    error_msg = result.message or "Falha ao criar a assinatura."
                else:
                    params = resolve_billing(self.request, self.request.user)
                    result = subscribe_plan(
                        plan,
                        billing_type=params.billing_type,
                        credit_card_token=params.credit_card_token,
                        remote_ip=params.remote_ip,
                    )
                    redirect_url = result.redirect_url
                    error_msg = result.message or "Falha ao criar a assinatura."
        except ValueError as exc:
            messages.error(self.request, str(exc) or "Falha ao criar a assinatura.")
            return redirect("services-plan-list")
        if result.ok:
            messages.success(self.request, "Assinatura criada. Aguardando o primeiro pagamento.")
            return redirect(redirect_url)
        order.status = Order.Status.CANCELED
        order.save(update_fields=["status", "updated_at"])
        plan.is_active = False
        plan.save(update_fields=["is_active", "updated_at"])
        messages.error(self.request, error_msg)
        return redirect("services-plan-list")


# --------------------------------------------------------------------------
# Prestador: visitas de manutenção


class MaintenanceVisitListView(ProviderRequiredMixin, ListView):
    template_name = "services/visits.html"
    context_object_name = "visits"
    paginate_by = 20

    def get_queryset(self):
        qs = MaintenanceVisit.objects.filter(completed_at__isnull=True, is_active=True)
        if not self.request.user.is_admin:
            qs = qs.filter(plan__prestador=self.request.user)
        return qs.select_related("plan", "plan__client", "plan__prestador").filter(plan__is_active=True)


class MaintenanceVisitCompleteView(ProviderRequiredMixin, View):
    def get_queryset(self):
        qs = MaintenanceVisit.objects.filter(pk=self.kwargs["pk"], is_active=True)
        if not self.request.user.is_admin:
            qs = qs.filter(plan__prestador=self.request.user)
        return qs

    def post(self, request, *args, **kwargs):
        visit = get_object_or_404(self.get_queryset())
        visit.completed_at = timezone.now()
        visit.save(update_fields=["completed_at", "updated_at"])
        messages.success(request, "Visita concluída.")
        return redirect("services-visits")
