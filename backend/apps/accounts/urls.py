from django.urls import path

from apps.accounts.views import RevealCredentialsView, TemporaryAccountDetailView, TemporaryAccountListView

urlpatterns = [
    path("accounts/", TemporaryAccountListView.as_view(), name="account-list"),
    path("accounts/<uuid:pk>/", TemporaryAccountDetailView.as_view(), name="account-detail"),
    path("accounts/<uuid:pk>/reveal-credentials/", RevealCredentialsView.as_view(), name="account-reveal"),
]
