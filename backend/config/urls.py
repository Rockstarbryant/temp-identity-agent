from django.contrib import admin
from django.urls import include, path, re_path

from apps.common.views import health
from apps.mcp_server import oauth
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
    path("api/", include("apps.email_service.urls")),
    path("api/", include("apps.profiles.urls")),
    path("api/", include("apps.mcp_server.urls")),
    path("api/", include("apps.notifications.urls")),
    path("mcp/", McpView.as_view(), name="mcp"),
    # OAuth for MCP clients such as claude.ai (discovery, registration, authorize, token)
    re_path(r"^\.well-known/oauth-protected-resource(?:/.*)?$", oauth.protected_resource_metadata),
    re_path(r"^\.well-known/oauth-authorization-server(?:/.*)?$", oauth.authorization_server_metadata),
    path("oauth/register", oauth.RegisterView.as_view(), name="oauth-register"),
    path("oauth/authorize", oauth.AuthorizeView.as_view(), name="oauth-authorize"),
    path("oauth/token", oauth.TokenView.as_view(), name="oauth-token"),
]
