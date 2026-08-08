from django.urls import path

from .views import (
    AddressCreateView,
    CheckoutView,
    cart_add_view,
    cart_remove_view,
    cart_view,
)

urlpatterns = [
    path("", cart_view, name="checkout-cart"),
    path("add/<uuid:product_pk>/", cart_add_view, name="checkout-cart-add"),
    path("remove/<uuid:product_pk>/", cart_remove_view, name="checkout-cart-remove"),
    path("finalizar/", CheckoutView.as_view(), name="checkout"),
    path("endereco/", AddressCreateView.as_view(), name="checkout-address"),
]
