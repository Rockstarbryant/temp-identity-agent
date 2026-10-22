from django.urls import path

from apps.accounts.chat_views import AccountChatView, ChatDetailView, ChatListView
from apps.accounts.mailbox_views import AccountMailboxAskView, AccountMailboxView, AccountMessageView
from apps.accounts.views import RevealCredentialsView, TemporaryAccountDetailView, TemporaryAccountListView

urlpatterns = [
    path("accounts/", TemporaryAccountListView.as_view(), name="account-list"),
    path("accounts/<uuid:pk>/", TemporaryAccountDetailView.as_view(), name="account-detail"),
    path("chats/", ChatListView.as_view(), name="chat-list"),
    path("chats/<uuid:pk>/", ChatDetailView.as_view(), name="chat-detail"),
    path("accounts/<uuid:pk>/chat/", AccountChatView.as_view(), name="account-chat"),
    path("accounts/<uuid:pk>/mailbox/", AccountMailboxView.as_view(), name="account-mailbox"),
    path("accounts/<uuid:pk>/mailbox/ask/", AccountMailboxAskView.as_view(), name="account-mailbox-ask"),
    path("accounts/<uuid:pk>/mailbox/messages/<uuid:message_id>/", AccountMessageView.as_view(), name="account-message"),
    path("accounts/<uuid:pk>/reveal-credentials/", RevealCredentialsView.as_view(), name="account-reveal"),
]
