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
