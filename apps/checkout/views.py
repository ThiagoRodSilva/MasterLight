"""Views de carrinho/pedido."""

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView

from apps.affiliate.models import AffiliateProfile, Referral
from apps.core.models import SiteSettings
from apps.payments.services import checkout_or_charge

from .models import Address, Cart, Order, OrderItem


def get_product_model():
    """Resolve o model Product em runtime (apps.get_model).

    Evita import estatico de apps.shop.models, eliminando o binding tardio
    dentro das funcoes de view e reduzindo acoplamento entre apps.
    """
    return apps.get_model("shop", "Product")


def cart_view(request):
    cart = Cart(request.session)
    return render(request, "checkout/cart.html", {"cart": cart})


def cart_add_view(request, product_pk):
    if not SiteSettings.load().store_enabled:
        messages.error(request, "A loja está indisponível no momento.")
        return redirect("home")
    if request.method != "POST":
        return redirect("shop-list")
    Product = get_product_model()
    product = get_object_or_404(Product, pk=product_pk, is_active=True)
    try:
        qty = int(request.POST.get("qty", 1) or 1)
    except (TypeError, ValueError):
        messages.error(request, "Quantidade inválida.")
        return redirect("shop-detail", slug=product.slug)
    if qty < 1:
        messages.error(request, "Quantidade deve ser maior que zero.")
        return redirect("shop-detail", slug=product.slug)
    if qty > product.stock:
        messages.error(request, "Quantidade acima do estoque disponível.")
        return redirect("shop-detail", slug=product.slug)
    cart = Cart(request.session)
    cart.add(product.pk, float(product.price), product.name, qty)
    messages.success(request, f"{product.name} adicionado ao carrinho.")
    return redirect("checkout-cart")


def cart_remove_view(request, product_pk):
    Cart(request.session).remove(product_pk)
    messages.info(request, "Item removido.")
    return redirect("checkout-cart")


class CheckoutView(LoginRequiredMixin, View):
    """Cria Order a partir do carrinho e dispara pagamento."""

    template_name = "checkout/checkout.html"

    def dispatch(self, request, *args, **kwargs):
        if not SiteSettings.load().store_enabled:
            messages.error(request, "A loja está indisponível no momento.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        cart = Cart(request.session)
        if cart.is_empty():
            return redirect("shop-list")
        return render(request, self.template_name, {"cart": cart})

    def post(self, request):
        cart = Cart(request.session)
        if cart.is_empty():
            return redirect("shop-list")
        Product = get_product_model()

        with transaction.atomic():
            order = Order.objects.create(user=request.user, status=Order.Status.AWAITING_PAYMENT)
            for line in cart:
                product = Product.objects.filter(pk=line["pk"], is_active=True).first()
                qty = int(line.get("qty", 0) or 0)
                if product is None or qty < 1 or qty > product.stock:
                    messages.error(
                        request,
                        f"Item '{line['name']}' não está mais disponível na quantidade pedida.",
                    )
                    cart.remove(line["pk"])
                    order.status = Order.Status.CANCELED
                    order.save(update_fields=["status", "updated_at"])
                    return redirect("checkout-cart")
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    name=product.name,
                    qty=qty,
                    unit_price=product.price,
                )
            order.recompute_total()

            # registra referral se cookie ref existir (nao-referencia a si mesmo)
            ref_code = request.COOKIES.get(settings.AFFILIATE_COOKIE_NAME) or request.session.get(
                settings.AFFILIATE_COOKIE_NAME
            )
            if ref_code:
                affil = AffiliateProfile.objects.filter(code=ref_code, is_active=True).first()
                if affil and affil.user_id != request.user.pk:
                    Referral.objects.create(
                        affiliate=affil,
                        referred=request.user,
                        order=order,
                        commission_rate=affil.commission_rate,
                        commission_amount=order.total * affil.commission_rate,
                    )

            # vincula o ultimo endereco salvo, se houver
            address = request.user.addresses.filter(is_active=True).first()
            if address:
                order.address = address
                order.save(update_fields=["address", "updated_at"])

            result = checkout_or_charge(
                order,
                request,
                address=address,
                fail_message="Falha ao iniciar pagamento.",
            )

        if result is None:
            return redirect("checkout-cart")
        cart.clear()
        messages.success(request, "Pedido criado. Aguardando confirmação do pagamento.")
        if "url" in result:
            return redirect(result["url"])
        return redirect(result["redirect_url"])


class AddressCreateView(LoginRequiredMixin, CreateView):
    model = Address
    fields = ["street", "number", "city", "state", "zip_code", "country"]
    template_name = "checkout/address_form.html"
    success_url = reverse_lazy("checkout")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)
