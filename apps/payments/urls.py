from django.urls import path

from .views import ManualConfirmationView, PixConfirmationView, WebhookView

urlpatterns = [
    path("webhook/", WebhookView.as_view(), name="payments-webhook"),
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
]
