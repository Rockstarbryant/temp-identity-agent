"""The vault's view of each account's mailbox."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import TemporaryAccount
from apps.audit.models import AuditLog
from apps.email_service import assistant, service, textutil
from apps.email_service.models import EmailMessage, TemporaryEmail


def _account_and_mailbox(request, pk):
    account = get_object_or_404(
        TemporaryAccount.objects.select_related("identity", "website", "job"), id=pk, job__user=request.user
    )
    if account.status == TemporaryAccount.Status.DELETED:
        return account, None, Response({"detail": "This account has been deleted."}, status=status.HTTP_410_GONE)
    mailbox = TemporaryEmail.objects.filter(identity=account.identity).first()
    if mailbox is None:
        return account, None, Response({"detail": "This account has no mailbox."}, status=status.HTTP_404_NOT_FOUND)
    return account, mailbox, None


def _summary(m: EmailMessage) -> dict:
    return {
        "id": str(m.id), "sender": m.sender, "subject": m.subject,
        "snippet": textutil.snippet(m.text_body, m.html_body),
        "received_at": m.received_at, "read": m.read_at is not None,
        "has_link": bool(m.extracted_link), "has_code": bool(m.extracted_otp),
    }


def _mailbox_info(mailbox: TemporaryEmail) -> dict:
    return {
        "address": mailbox.address,
        "status": "active" if service.mailbox_is_pollable(mailbox) else "closed",
        "own_inbox": mailbox.provider in ("imap", "gmail"),
        "expires_at": mailbox.expires_at,
        "last_checked_at": mailbox.last_polled_at,
    }


class AccountMailboxView(APIView):
    """
    GET /api/accounts/{id}/mailbox/            — saved messages (newest first).
    GET /api/accounts/{id}/mailbox/?refresh=1  — check for new mail first.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        account, mailbox, error = _account_and_mailbox(request, pk)
        if error:
            return error
        refresh_error = ""
        if request.query_params.get("refresh") and service.mailbox_is_pollable(mailbox):
            try:
                service.sync_new_messages(mailbox)
            except Exception:  # noqa: BLE001
                refresh_error = "Could not check for new mail just now. Showing what was already saved."
        messages = EmailMessage.objects.filter(mailbox=mailbox).order_by("-received_at", "-created_at")[:100]
        items = [_summary(m) for m in messages]
        return Response({
            "mailbox": _mailbox_info(mailbox), "messages": items,
            "unread": sum(1 for i in items if not i["read"]), "refresh_error": refresh_error,
        })


class AccountMessageView(APIView):
    """GET /api/accounts/{id}/mailbox/messages/{message_id}/ — full text (never HTML) and links; marks it read."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk, message_id):
        account, mailbox, error = _account_and_mailbox(request, pk)
        if error:
            return error
        message = get_object_or_404(EmailMessage, id=message_id, mailbox=mailbox)
        if message.read_at is None:
            message.read_at = timezone.now()
            message.save(update_fields=["read_at", "updated_at"])
        return Response({
            **_summary(message),
            "text": textutil.plain_text(message.text_body, message.html_body),
            "links": textutil.all_links(message.text_body, message.html_body),
            "verification_link": message.extracted_link, "code": message.extracted_otp,
        })


class AccountMailboxAskView(APIView):
    """POST /api/accounts/{id}/mailbox/ask/ {"question": "..."} — the agent checks the mailbox and answers."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mailbox_ask"

    def post(self, request, pk):
        account, mailbox, error = _account_and_mailbox(request, pk)
        if error:
            return error
        question = str(request.data.get("question", "")).strip()
        if len(question) < 3:
            return Response({"detail": "Ask a question, for example “Did the verification email arrive?”"},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            result = assistant.answer_question(mailbox, question)
        except assistant.AssistantUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        AuditLog.objects.create(user=request.user, action="mailbox.asked", resource_type="TemporaryAccount",
                                resource_id=str(account.id))
        return Response(result)


class AccountChatView(APIView):
    """
    GET    /api/accounts/{id}/chat/ — the conversation, and the website task running now, if any.
    POST   /api/accounts/{id}/chat/ {"message": "..."} — talk to the agent about this account.
    DELETE /api/accounts/{id}/chat/ — clear the conversation.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        return [ScopedRateThrottle()] if self.request.method == "POST" else []

    throttle_scope = "account_chat"

    def _account(self, request, pk):
        account = get_object_or_404(
            TemporaryAccount.objects.select_related("identity", "website", "job"), id=pk, job__user=request.user)
        if account.status == TemporaryAccount.Status.DELETED:
            return None
        return account

    @staticmethod
    def _item(m):
        return {"id": str(m.id), "role": m.role, "kind": m.kind, "content": m.content,
                "job_id": str(m.job_id) if m.job_id else None, "created_at": m.created_at}

    def _state(self, account):
        from apps.accounts.chat import _active_task, history

        active = _active_task(account)
        return {"messages": [self._item(m) for m in history(account)],
                "active_job": {"id": str(active.id), "state": active.state} if active else None,
                "can_chat": account.status == TemporaryAccount.Status.ACTIVE}

    def get(self, request, pk):
        account = self._account(request, pk)
        if account is None:
            return Response({"detail": "This account has been deleted."}, status=status.HTTP_410_GONE)
        return Response(self._state(account))

    def post(self, request, pk):
        from apps.accounts import chat

        account = self._account(request, pk)
        if account is None:
            return Response({"detail": "This account has been deleted."}, status=status.HTTP_410_GONE)
        if account.status != TemporaryAccount.Status.ACTIVE:
            return Response({"detail": "This account has expired, so the agent can't act on it."}, status=status.HTTP_400_BAD_REQUEST)
        text = str(request.data.get("message", "")).strip()
        if not text:
            return Response({"detail": "Write a message first."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            chat.send(account, request.user, text, ip=request.META.get("REMOTE_ADDR"))
        except chat.ChatUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(self._state(account))

    def delete(self, request, pk):
        account = self._account(request, pk)
        if account is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        account.chat_messages.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChatListView(APIView):
    """GET /api/chats/ — every vault account as a conversation, most recently active first."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.accounts.models import AccountChatMessage
        from apps.registration.models import RegistrationJob

        accounts = list(
            TemporaryAccount.objects.filter(job__user=request.user).exclude(status=TemporaryAccount.Status.DELETED)
            .select_related("identity", "website")
        )
        ids = [a.id for a in accounts]
        last, counts = {}, {}
        for m in AccountChatMessage.objects.filter(account_id__in=ids).order_by("-created_at")[:2000]:
            last.setdefault(m.account_id, m)
            counts[m.account_id] = counts.get(m.account_id, 0) + 1
        working = set(
            RegistrationJob.objects.filter(
                identity_id__in=[a.identity_id for a in accounts], kind=RegistrationJob.Kind.ACCOUNT_TASK)
            .exclude(state__in=RegistrationJob.TERMINAL_STATES).values_list("identity_id", flat=True)
        )
        items = []
        for a in accounts:
            m = last.get(a.id)
            items.append({
                "account_id": str(a.id), "domain": a.website.domain, "email": a.identity.email, "status": a.status,
                "message_count": counts.get(a.id, 0), "working": a.identity_id in working,
                "last_message": {"role": m.role, "content": m.content[:140], "created_at": m.created_at} if m else None,
                "last_activity": (m.created_at if m else a.created_at),
            })
        items.sort(key=lambda i: i["last_activity"], reverse=True)
        return Response({"results": items})
