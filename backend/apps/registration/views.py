from urllib.parse import urlparse

from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.common.exceptions import TempIdentityAgentError
from apps.common.permissions import IsOwner
from apps.registration.models import RegistrationJob, TargetWebsite
from apps.registration.serializers import (
    RegistrationJobCreateSerializer,
    RegistrationJobDetailSerializer,
    RegistrationJobSerializer,
)
from apps.registration.tasks import resume_registration_job_task, run_registration_job_task


class RegistrationJobListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/registration-jobs/  — the user's own jobs
    POST /api/registration-jobs/  — {"url": "..."} -> creates + enqueues a job
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "registration_jobs"

    def get_queryset(self):
        return (
            RegistrationJob.objects.filter(user=self.request.user, dismissed_at__isnull=True)
            .select_related("target_website", "identity", "agent_session", "account")
        )

    def get_serializer_class(self):
        return RegistrationJobCreateSerializer if self.request.method == "POST" else RegistrationJobSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        url = serializer.validated_data["url"]
        domain = urlparse(url).hostname
        if not domain:
            raise ValidationError({"url": "Could not determine a domain from this URL."})

        target_website, _ = TargetWebsite.objects.get_or_create(
            domain=domain, defaults={"registration_url": url}
        )
        job = RegistrationJob.objects.create(user=request.user, target_website=target_website)

        AuditLog.objects.create(
            user=request.user, action="job.created", resource_type="RegistrationJob",
            resource_id=str(job.id), metadata={"domain": domain},
        )
        run_registration_job_task.delay(str(job.id))
        job.refresh_from_db()  # the task may have already run (sync/eager) or a worker
                                 # may be racing us — always return the current DB state,
                                 # never the pre-dispatch in-memory object.

        return Response(RegistrationJobSerializer(job).data, status=status.HTTP_201_CREATED)


class RegistrationJobDetailView(generics.RetrieveDestroyAPIView):
    """
    GET    /api/registration-jobs/{id}/ — full detail including step history.
    DELETE /api/registration-jobs/{id}/ — remove a finished job from the dashboard.

    Delete hides the job (soft-delete). The vault account created by a
    completed job is NOT touched — delete that from the vault itself.
    A job that is still running must be cancelled first.
    """

    serializer_class = RegistrationJobDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return (
            RegistrationJob.objects.filter(user=self.request.user, dismissed_at__isnull=True)
            .select_related("target_website", "identity", "agent_session", "account")
            .prefetch_related("steps")
        )

    def destroy(self, request, *args, **kwargs):
        job = self.get_object()
        if job.state in RegistrationJob.ACTIVE_STATES:
            return Response(
                {"detail": "This job is still running. Cancel it before deleting."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        job.dismissed_at = timezone.now()
        job.save(update_fields=["dismissed_at", "updated_at"])
        AuditLog.objects.create(
            user=request.user, action="job.dismissed", resource_type="RegistrationJob",
            resource_id=str(job.id),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegistrationJobRetryView(APIView):
    """
    POST /api/registration-jobs/{id}/retry/ — start a fresh job for the same
    site. The original stays as a record of the failed attempt.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "registration_jobs"

    RETRYABLE_STATES = {
        RegistrationJob.State.FAILED,
        RegistrationJob.State.CANCELLED,
        RegistrationJob.State.EXPIRED,
    }

    def post(self, request, pk):
        old = _get_owned_job_or_404(request.user, pk)
        if old.state not in self.RETRYABLE_STATES:
            return Response(
                {"detail": f"Only failed, cancelled or expired jobs can be retried (this one is {old.state!r})."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        job = RegistrationJob.objects.create(user=request.user, target_website=old.target_website)
        AuditLog.objects.create(
            user=request.user, action="job.retried", resource_type="RegistrationJob",
            resource_id=str(job.id), metadata={"retry_of": str(old.id), "domain": old.target_website.domain},
        )
        run_registration_job_task.delay(str(job.id))
        job.refresh_from_db()
        return Response(RegistrationJobSerializer(job).data, status=status.HTTP_201_CREATED)


class RegistrationJobClearFinishedView(APIView):
    """
    POST /api/registration-jobs/clear-finished/ — hide every failed, cancelled
    and expired job at once. Completed jobs are left alone.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        cleared = RegistrationJob.objects.filter(
            user=request.user,
            dismissed_at__isnull=True,
            state__in=[
                RegistrationJob.State.FAILED,
                RegistrationJob.State.CANCELLED,
                RegistrationJob.State.EXPIRED,
            ],
        ).update(dismissed_at=timezone.now())
        AuditLog.objects.create(
            user=request.user, action="job.cleared_finished", resource_type="RegistrationJob",
            resource_id="", metadata={"count": cleared},
        )
        return Response({"cleared": cleared}, status=status.HTTP_200_OK)


class RegistrationJobResumeView(APIView):
    """POST /api/registration-jobs/{id}/resume/ — resume a paused (CAPTCHA/human-action) job."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        job = _get_owned_job_or_404(request.user, pk)
        try:
            from apps.registration.orchestration import resume_registration_job  # noqa: F401 (validated below)

            if job.state not in RegistrationJob.RESUMABLE_STATES:
                return Response(
                    {"detail": f"Job is in state {job.state!r}, which cannot be resumed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except TempIdentityAgentError as exc:
            return Response({"detail": exc.message}, status=status.HTTP_400_BAD_REQUEST)

        resume_registration_job_task.delay(str(job.id))
        AuditLog.objects.create(
            user=request.user, action="job.resume_requested", resource_type="RegistrationJob", resource_id=str(job.id)
        )
        return Response({"detail": "Resume requested.", "id": str(job.id)}, status=status.HTTP_202_ACCEPTED)


class RegistrationJobCancelView(APIView):
    """POST /api/registration-jobs/{id}/cancel/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        job = _get_owned_job_or_404(request.user, pk)
        from apps.registration.orchestration import cancel_registration_job

        try:
            job = cancel_registration_job(job.id)
        except TempIdentityAgentError as exc:
            return Response({"detail": exc.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(RegistrationJobSerializer(job).data, status=status.HTTP_200_OK)


def _get_owned_job_or_404(user, pk):
    from django.shortcuts import get_object_or_404

    return get_object_or_404(RegistrationJob, id=pk, user=user)
