from django.urls import path

from .views import (
    BoletoConfirmationView,
    CardConfirmationView,
    ManualConfirmationView,
    OrderStatusView,
    PixConfirmationView,
    ReconcilePaymentsView,
    WebhookView,
)

urlpatterns = [
    path("webhook/", WebhookView.as_view(), name="payments-webhook"),
    path("reconciliar/", ReconcilePaymentsView.as_view(), name="payments-reconcile"),
    path(
        "manual/<uuid:order_pk>/",
        ManualConfirmationView.as_view(),
        name="payments-manual-confirm",
    ),
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
        "boleto/<uuid:order_pk>/",
        BoletoConfirmationView.as_view(),
        name="payments-boleto-confirm",
    ),
    path(
        "status/<uuid:order_pk>/",
        OrderStatusView.as_view(),
        name="payments-status",
    ),
]
