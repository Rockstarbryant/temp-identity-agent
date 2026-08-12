from django.urls import path

from apps.identities.views import IdentityDetailView, IdentityListView

urlpatterns = [
    path("identities/", IdentityListView.as_view(), name="identity-list"),
    path("identities/<uuid:pk>/", IdentityDetailView.as_view(), name="identity-detail"),
]
