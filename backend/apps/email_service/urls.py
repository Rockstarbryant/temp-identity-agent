from django.urls import path

from apps.email_service import inbox_views

urlpatterns = [
    path("inbox/", inbox_views.InboxView.as_view(), name="inbox"),
    path("inbox/ask/", inbox_views.InboxAskView.as_view(), name="inbox-ask"),
    path("inbox/messages/<uuid:message_id>/", inbox_views.InboxMessageView.as_view(), name="inbox-message"),
]
