from django.contrib import admin
from django.urls import include, path

from apps.users.views import MeView

# Further app-level URL includes (apps.registration.urls, apps.accounts.urls,
# etc.) get added here as each app grows real endpoints in later phases.
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.users.urls")),
    path("api/me/", MeView.as_view(), name="me"),
    path("api/", include("apps.identities.urls")),
    path("api/", include("apps.registration.urls")),
    path("api/", include("apps.accounts.urls")),
]
