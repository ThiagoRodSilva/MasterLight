from django.urls import path

from .views import (
    MyServiceRequestListView,
    ProviderServiceRequestListView,
    ServiceCreateView,
    ServiceDeleteView,
    ServiceDetailView,
    ServiceListView,
    ServiceListViewMine,
    ServiceQuoteView,
    ServiceRequestApproveView,
    ServiceRequestCancelView,
    ServiceRequestCreateView,
    ServiceRequestPayLinkView,
    ServiceUpdateView,
)

urlpatterns = [
    path("", ServiceListView.as_view(), name="services-list"),
    path("meus-servicos/", ServiceListViewMine.as_view(), name="services-my"),
    path("novo-servico/", ServiceCreateView.as_view(), name="services-create"),
    path("<uuid:pk>/excluir/", ServiceDeleteView.as_view(), name="services-delete"),
    path(
        "prestador/solicitacoes/",
        ProviderServiceRequestListView.as_view(),
        name="services-provider-requests",
    ),
    path("minhas-solicitacoes/", MyServiceRequestListView.as_view(), name="services-my-requests"),
    path(
        "minhas-solicitacoes/<uuid:pk>/aprovar/",
        ServiceRequestApproveView.as_view(),
        name="services-request-approve",
    ),
    path(
        "minhas-solicitacoes/<uuid:pk>/link-pagamento/",
        ServiceRequestPayLinkView.as_view(),
        name="services-request-paylink",
    ),
    path(
        "minhas-solicitacoes/<uuid:pk>/cancelar/",
        ServiceRequestCancelView.as_view(),
        name="services-request-cancel",
    ),
    path(
        "solicitacoes/<uuid:pk>/orcar/", ServiceQuoteView.as_view(), name="services-request-quote"
    ),
    path("<slug:slug>/editar/", ServiceUpdateView.as_view(), name="services-update"),
    path("<slug:slug>/", ServiceDetailView.as_view(), name="services-detail"),
    path("<slug:slug>/solicitar/", ServiceRequestCreateView.as_view(), name="services-request"),
]
