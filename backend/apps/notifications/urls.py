from django.urls import path

from apps.notifications import views

urlpatterns = [
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path("notifications/read/", views.NotificationReadView.as_view(), name="notifications-read"),
    path("notifications/stream/", views.NotificationStreamView.as_view(), name="notifications-stream"),
    path("notifications/<int:pk>/", views.NotificationDetailView.as_view(), name="notification-detail"),
]
