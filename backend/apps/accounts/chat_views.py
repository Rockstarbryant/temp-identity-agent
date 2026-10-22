"""Chat API: a list of conversations, and one conversation at a time."""
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import chat
from apps.accounts.models import ChatConversation, TemporaryAccount


def _item(m):
    return {"id": str(m.id), "role": m.role, "kind": m.kind, "content": m.content, "actions": m.actions or [],
            "job_id": str(m.job_id) if m.job_id else None, "created_at": m.created_at}


def _state(convo: ChatConversation) -> dict:
    account = convo.account
    active = chat.running_jobs(convo)
    can_chat = account.status == TemporaryAccount.Status.ACTIVE if account else True
    return {
        "id": str(convo.id), "title": chat.title_of(convo), "account_id": str(account.id) if account else None,
        "account_status": account.status if account else None, "can_chat": can_chat,
        "messages": [_item(m) for m in chat.history(convo)],
        "active_job": {"id": str(active[0].id), "state": active[0].state} if active else None,
    }


def _owned(request, pk) -> ChatConversation | None:
    convo = get_object_or_404(ChatConversation.objects.select_related("account", "account__website", "account__identity"),
                              id=pk, user=request.user)
    if convo.account_id and convo.account.status == TemporaryAccount.Status.DELETED:
        return None
    return convo


class _ConversationAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "account_chat"

    def get_throttles(self):
        return [ScopedRateThrottle()] if self.request.method == "POST" else []

    def convo(self, request, pk) -> ChatConversation | None:
        raise NotImplementedError

    def get(self, request, pk):
        convo = self.convo(request, pk)
        if convo is None:
            return Response({"detail": "This account has been deleted."}, status=status.HTTP_410_GONE)
        return Response(_state(convo))

    def post(self, request, pk):
        convo = self.convo(request, pk)
        if convo is None:
            return Response({"detail": "This account has been deleted."}, status=status.HTTP_410_GONE)
        if convo.account_id and convo.account.status != TemporaryAccount.Status.ACTIVE:
            return Response({"detail": "This account has expired, so the agent can't act on it."}, status=status.HTTP_400_BAD_REQUEST)
        text = str(request.data.get("message", "")).strip()
        if not text:
            return Response({"detail": "Write a message first."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            chat.send(convo, request.user, text, ip=request.META.get("REMOTE_ADDR"))
        except chat.ChatUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        convo.refresh_from_db()  # a finished task may have linked it to an account
        return Response(_state(convo))

    def delete(self, request, pk):
        convo = self.convo(request, pk)
        if convo is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        if convo.account_id:
            convo.messages.all().delete()  # an account's conversation stays; only its history is cleared
        else:
            convo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChatDetailView(_ConversationAPI):
    """GET / POST {"message"} / DELETE /api/chats/{id}/"""

    def convo(self, request, pk):
        return _owned(request, pk)


class AccountChatView(_ConversationAPI):
    """The same, addressed by vault account: /api/accounts/{id}/chat/"""

    def convo(self, request, pk):
        account = get_object_or_404(TemporaryAccount.objects.select_related("identity", "website", "job"),
                                    id=pk, job__user=request.user)
        if account.status == TemporaryAccount.Status.DELETED:
            return None
        convo = chat.conversation_for_account(account)
        convo.account = account
        return convo


class ChatListView(APIView):
    """
    GET  /api/chats/ — all conversations, most recently active first. Every vault account has one.
    POST /api/chats/ — start an empty conversation ("New chat").
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.registration.models import RegistrationJob

        accounts = list(
            TemporaryAccount.objects.filter(job__user=request.user).exclude(status=TemporaryAccount.Status.DELETED)
            .select_related("identity", "website", "job")
        )
        existing = set(ChatConversation.objects.filter(account__in=accounts).values_list("account_id", flat=True))
        for a in accounts:
            if a.id not in existing:
                chat.conversation_for_account(a)

        convos = list(
            ChatConversation.objects.filter(user=request.user).exclude(account__status=TemporaryAccount.Status.DELETED)
            .select_related("account", "account__website", "account__identity")
        )
        last, counts = {}, {}
        from apps.accounts.models import AccountChatMessage

        for m in AccountChatMessage.objects.filter(conversation__in=convos).order_by("-created_at")[:3000]:
            last.setdefault(m.conversation_id, m)
            counts[m.conversation_id] = counts.get(m.conversation_id, 0) + 1
        job_ids = set(AccountChatMessage.objects.filter(conversation__in=convos, job__isnull=False).values_list("job_id", flat=True))
        busy = set(
            AccountChatMessage.objects.filter(
                job_id__in=RegistrationJob.objects.filter(id__in=job_ids).exclude(state__in=RegistrationJob.TERMINAL_STATES).values("id"),
            ).values_list("conversation_id", flat=True)
        )
        items = []
        for c in convos:
            m = last.get(c.id)
            if c.account_id is None and m is None:
                continue  # an empty "New chat" shows only in the browser that opened it
            items.append({
                "id": str(c.id), "title": chat.title_of(c), "account_id": str(c.account_id) if c.account_id else None,
                "email": c.account.identity.email if c.account_id else "", "status": c.account.status if c.account_id else "active",
                "message_count": counts.get(c.id, 0), "working": c.id in busy,
                "last_message": {"role": m.role, "content": m.content[:140], "created_at": m.created_at} if m else None,
                "last_activity": (m.created_at if m else c.created_at),
            })
        items.sort(key=lambda i: i["last_activity"], reverse=True)
        return Response({"results": items})

    def post(self, request):
        convo = ChatConversation.objects.create(user=request.user)
        return Response(_state(convo), status=status.HTTP_201_CREATED)
