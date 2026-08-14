"""URLs de accounts: perfil publico e meus dados (allauth trata login)."""

from django.urls import path

from .views import ProfileDetailView, ProfileEditView, me_view

urlpatterns = [
    path("me/", me_view, name="accounts-me"),
    path("me/editar/", ProfileEditView.as_view(), name="accounts-me-edit"),
    path("u/<str:username>/", ProfileDetailView.as_view(), name="accounts-profile"),
]
