from django.contrib import admin
from django.urls import include, path

from apps.common.views import health
from apps.mcp_server.views import McpView
from apps.users.views import MeView

urlpatterns = [
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.users.urls")),
    path("api/me/", MeView.as_view(), name="me"),
    path("api/", include("apps.identities.urls")),
    path("api/", include("apps.registration.urls")),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.profiles.urls")),
    path("api/", include("apps.mcp_server.urls")),
    path("mcp/", McpView.as_view(), name="mcp"),
]
