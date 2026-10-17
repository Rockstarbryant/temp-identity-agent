from django.urls import path

from apps.mcp_server.views import ApiKeyDetailView, ApiKeyListCreateView

urlpatterns = [
    path("api-keys/", ApiKeyListCreateView.as_view(), name="api-keys"),
    path("api-keys/<uuid:pk>/", ApiKeyDetailView.as_view(), name="api-key-detail"),
]
