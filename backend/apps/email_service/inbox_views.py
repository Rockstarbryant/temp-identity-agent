"""The connected inbox: one inbox for everything the user's own Gmail/IMAP mailbox has collected."""
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.email_service import assistant, inbox, service, textutil
from apps.email_service.models import EmailMessage
from apps.profiles.models import EmailConnection


def _connection(request):
    return EmailConnection.objects.filter(user=request.user).first()


def _not_connected():
    return Response({"detail": "No email is connected. Connect one in Settings."}, status=status.HTTP_404_NOT_FOUND)


def _summary(m: EmailMessage, read: bool, site: dict | None) -> dict:
    return {
        "id": str(m.id), "sender": m.sender, "subject": m.subject,
        "snippet": textutil.snippet(m.text_body, m.html_body),
        "received_at": m.received_at, "read": read,
        "has_link": bool(m.extracted_link), "has_code": bool(m.extracted_otp),
        "site": site["domain"] if site else "", "account_id": site["account_id"] if site else "",
    }


def _read_ids(user) -> set[str]:
    return set(EmailMessage.objects.filter(mailbox__in=inbox.own_mailboxes(user), read_at__isnull=False)
               .values_list("external_id", flat=True))


class InboxView(APIView):
    """
    GET /api/inbox/            — everything saved from the connected inbox (newest first).
    GET /api/inbox/?refresh=1  — check for new mail first (works even when muted).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        conn = _connection(request)
        if conn is None:
            return _not_connected()
        refresh_error = ""
        primary = inbox.primary_mailbox(request.user)
        if request.query_params.get("refresh") and primary is not None:
            try:
                service.sync_new_messages(primary)
            except Exception:  # noqa: BLE001
                refresh_error = "Could not check for new mail just now. Showing what was already saved."
        read = _read_ids(request.user)
        domains = inbox._site_labels(request.user)
        items = [_summary(m, m.external_id in read, inbox.guess_site(m, domains)) for m in inbox.inbox_messages(request.user)]
        return Response({
            "mailbox": {
                "address": conn.address, "status": "active" if primary is not None else "idle",
                "own_inbox": True, "expires_at": None,
                "last_checked_at": primary.last_polled_at if primary else None,
                "muted": conn.muted, "kind": conn.kind,
            },
            "messages": items, "unread": sum(1 for i in items if not i["read"]), "refresh_error": refresh_error,
        })


class InboxMessageView(APIView):
    """GET /api/inbox/messages/{id}/ — full text (never HTML) and links; marks it read."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, message_id):
        message = get_object_or_404(EmailMessage, id=message_id, mailbox__in=inbox.own_mailboxes(request.user))
        inbox.mark_read(request.user, message)
        site = inbox.guess_site(message, inbox._site_labels(request.user))
        return Response({
            **_summary(message, True, site),
            "text": textutil.plain_text(message.text_body, message.html_body),
            "links": textutil.all_links(message.text_body, message.html_body),
            "verification_link": message.extracted_link, "code": message.extracted_otp,
        })


class InboxAskView(APIView):
    """POST /api/inbox/ask/ {"question": "..."} — the assistant reads the recent inbox and answers."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mailbox_ask"

    def post(self, request):
        if _connection(request) is None:
            return _not_connected()
        question = str(request.data.get("question", "")).strip()
        if len(question) < 3:
            return Response({"detail": "Ask a question, for example “Did the verification email arrive?”"},
                            status=status.HTTP_400_BAD_REQUEST)
        new_count = 0
        primary = inbox.primary_mailbox(request.user)
        if primary is not None:
            try:
                new_count = len(service.sync_new_messages(primary))
            except Exception:  # noqa: BLE001
                pass
        try:
            result = assistant.answer_from_messages(inbox.inbox_messages(request.user, 15), question, new_count)
        except assistant.AssistantUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        AuditLog.objects.create(user=request.user, action="inbox.asked", resource_type="EmailConnection",
                                resource_id=str(request.user.id))
        return Response(result)
