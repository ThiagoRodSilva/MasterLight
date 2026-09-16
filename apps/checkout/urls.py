from django.urls import path

from .views import AddressCreateView

urlpatterns = [
    path("endereco/", AddressCreateView.as_view(), name="checkout-address"),
]