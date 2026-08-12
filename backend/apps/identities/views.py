from rest_framework import generics, permissions

from apps.common.permissions import IsOwner
from apps.identities.models import TemporaryIdentity
from apps.identities.serializers import TemporaryIdentitySerializer


class IdentityListView(generics.ListAPIView):
    """GET /api/identities/ — the requesting user's own temporary identities."""

    serializer_class = TemporaryIdentitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TemporaryIdentity.objects.filter(user=self.request.user)


class IdentityDetailView(generics.RetrieveAPIView):
    """
    GET /api/identities/{id}/ — a single identity, owner-only.

    The queryset itself is scoped to the requesting user (not just the
    IsOwner permission check) so a non-owner gets a clean 404 instead of
    a 403 that would confirm the object exists — avoids leaking identity
    IDs belonging to other users.
    """

    serializer_class = TemporaryIdentitySerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return TemporaryIdentity.objects.filter(user=self.request.user)
