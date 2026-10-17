from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import TemporaryAccount
from apps.accounts.serializers import RevealCredentialsResponseSerializer, TemporaryAccountSerializer
from apps.audit.models import AuditLog
from apps.common.permissions import IsOwner


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


class TemporaryAccountListView(generics.ListAPIView):
    """GET /api/accounts/ — the user's vault."""

    serializer_class = TemporaryAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TemporaryAccount.objects.filter(job__user=self.request.user).select_related(
            "identity", "website", "job"
        )


class TemporaryAccountDetailView(generics.RetrieveDestroyAPIView):
    """
    GET    /api/accounts/{id}/ — metadata only, no credentials.
    DELETE /api/accounts/{id}/ — soft-delete the vault entry AND scrub the
                                  underlying secrets (identity password,
                                  mailbox credential), not just flip a flag.
    """

    serializer_class = TemporaryAccountSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return TemporaryAccount.objects.filter(job__user=self.request.user).select_related(
            "identity", "website", "job"
        )

    def perform_destroy(self, account):
        account.status = TemporaryAccount.Status.DELETED
        account.save(update_fields=["status", "updated_at"])

        identity = account.identity
        identity.encrypted_password = ""
        identity.status = identity.Status.REVOKED
        identity.save(update_fields=["encrypted_password", "status", "updated_at"])

        from apps.email_service.models import TemporaryEmail

        TemporaryEmail.objects.filter(identity=identity).update(encrypted_credential="")

        AuditLog.objects.create(
            user=self.request.user, action="account.deleted", resource_type="TemporaryAccount",
            resource_id=str(account.id), ip_address=_client_ip(self.request),
        )


class RevealCredentialsView(APIView):
    """
    POST /api/accounts/{id}/reveal-credentials/

    Requires an authenticated request (same JWT as everything else in
    this API) — every reveal is audit-logged with the requesting IP,
    since this is the one endpoint in the system that returns a
    plaintext secret.
    """

    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_object(self):
        from django.shortcuts import get_object_or_404

        account = get_object_or_404(
            TemporaryAccount.objects.select_related("identity", "website", "job"),
            id=self.kwargs["pk"], job__user=self.request.user,
        )
        self.check_object_permissions(self.request, account)
        return account

    def post(self, request, pk):
        account = self.get_object()
        if account.status == TemporaryAccount.Status.DELETED:
            return Response({"detail": "This account has been deleted."}, status=status.HTTP_410_GONE)

        account.revealed_at = timezone.now()
        account.save(update_fields=["revealed_at", "updated_at"])

        AuditLog.objects.create(
            user=request.user, action="account.credentials_revealed", resource_type="TemporaryAccount",
            resource_id=str(account.id), ip_address=_client_ip(request),
        )

        data = RevealCredentialsResponseSerializer({
            "email": account.identity.email,
            "username": account.identity.username,
            "password": account.identity.get_password(),
            "domain": account.website.domain,
            "expires_at": account.identity.expires_at,
            "permanent": account.job.account_mode == "permanent",
        }).data
        return Response(data, status=status.HTTP_200_OK)
