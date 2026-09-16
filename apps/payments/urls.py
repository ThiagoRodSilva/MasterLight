from django.urls import path

from .views import (
    CardConfirmationView,
    CheckoutCallbackView,
    OrderStatusView,
    PixConfirmationView,
    ReconcilePaymentsView,
    WebhookView,
)

urlpatterns = [
    path("webhook/", WebhookView.as_view(), name="payments-webhook"),
    path("reconciliar/", ReconcilePaymentsView.as_view(), name="payments-reconcile"),
    path(
        "pix/<uuid:order_pk>/",
        PixConfirmationView.as_view(),
        name="payments-pix-confirm",
    ),
    path(
        "cartao/<uuid:order_pk>/",
        CardConfirmationView.as_view(),
        name="payments-card-confirm",
    ),
    path(
        "checkout/<uuid:order_pk>/<str:outcome>/",
        CheckoutCallbackView.as_view(),
        name="payments-checkout-callback",
    ),
    path(
        "status/<uuid:order_pk>/",
        OrderStatusView.as_view(),
        name="payments-status",
    ),
]
