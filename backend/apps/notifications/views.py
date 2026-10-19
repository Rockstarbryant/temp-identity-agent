from django.http import StreamingHttpResponse
from rest_framework import permissions, status
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications import service
from apps.notifications.models import Notification
from apps.notifications.stream import stream


class AnyAcceptNegotiation(DefaultContentNegotiation):
    """The stream answers `Accept: text/event-stream`, which DRF would otherwise reject with 406."""

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


class NotificationListView(APIView):
    """
    GET    /api/notifications/ — newest first (max 100) plus the unread count.
    DELETE /api/notifications/ — clear all of them.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        items = Notification.objects.filter(user=request.user)[:100]
        return Response({"unread": service.unread_count(request.user), "results": [service.serialize(n) for n in items]})

    def delete(self, request):
        Notification.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationReadView(APIView):
    """POST /api/notifications/read/ — {"ids": [1, 2]} marks those read; no ids marks everything read."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ids = request.data.get("ids")
        if ids is not None:
            if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
                return Response({"detail": "ids must be a list of numbers."}, status=status.HTTP_400_BAD_REQUEST)
        service.mark_read(request.user, ids)
        return Response({"unread": service.unread_count(request.user)})


class NotificationDetailView(APIView):
    """DELETE /api/notifications/{id}/"""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        Notification.objects.filter(user=request.user, id=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationStreamView(APIView):
    """
    GET /api/notifications/stream/ — Server-Sent Events.

    The browser's EventSource cannot send an Authorization header, so the frontend reads this
    stream with fetch() and the normal bearer token. `Last-Event-ID` (or ?last_id=) resumes
    after a reconnect.
    """

    permission_classes = [permissions.IsAuthenticated]
    content_negotiation_class = AnyAcceptNegotiation

    def get(self, request):
        raw = request.headers.get("Last-Event-ID") or request.query_params.get("last_id") or ""
        try:
            last_id = int(raw)
        except ValueError:
            last_id = 0
        if not raw:
            # A fresh connection only wants what happens from now on; history comes from the list endpoint.
            latest = Notification.objects.filter(user=request.user).values_list("id", flat=True).first()
            last_id = latest or 0

        response = StreamingHttpResponse(stream(request.user, last_id), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"  # tell nginx-style proxies not to buffer
        return response
