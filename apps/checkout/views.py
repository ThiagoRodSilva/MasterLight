"""Views de carrinho/pedido."""

from django.apps import apps
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView

from apps.core.mixins import ClienteRequiredMixin
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


class CheckoutView(ClienteRequiredMixin, View):
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
            product_pks = [line["pk"] for line in cart]
            products_qs = Product.objects.filter(pk__in=product_pks, is_active=True)
            # in_bulk() com field_name='pk' retorna dict com chaves string para compatibilidade
            products = {str(p.pk): p for p in products_qs}
            for line in cart:
                product = products.get(line["pk"])
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
            from django.conf import settings

            from apps.affiliate.services import create_referral

            ref_code = request.COOKIES.get(settings.AFFILIATE_COOKIE_NAME)
            if ref_code:
                create_referral(ref_code, request.user, order)

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


class AddressCreateView(ClienteRequiredMixin, CreateView):
    model = Address
    fields = ["street", "number", "city", "state", "zip_code", "country"]
    template_name = "checkout/address_form.html"
    success_url = reverse_lazy("checkout")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)
