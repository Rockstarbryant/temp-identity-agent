from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.browser import live_view
from apps.common.exceptions import TempIdentityAgentError
from apps.common.permissions import IsOwner
from apps.registration.jobs import create_job
from apps.registration.models import AgentQuestion, RegistrationJob
from apps.registration.serializers import (
    LiveInputSerializer,
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
        job = create_job(request.user, serializer.validated_data["url"])
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
        job = create_job(
            request.user, old.target_url or old.target_website.registration_url,
            source=old.source, goal=old.goal, account_mode=old.account_mode, kind=old.kind,
            audit_extra={"retry_of": str(old.id)},
        )
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

        if live_view.is_holding(job.id):
            # The worker is still holding this job's browser open: tell it to
            # carry on in that same browser instead of starting a new one.
            live_view.signal_done(job.id)
        else:
            resume_registration_job_task.delay(str(job.id))
        AuditLog.objects.create(
            user=request.user, action="job.resume_requested", resource_type="RegistrationJob", resource_id=str(job.id)
        )
        return Response({"detail": "Resume requested.", "id": str(job.id)}, status=status.HTTP_202_ACCEPTED)


class RegistrationJobLiveView(APIView):
    """
    GET /api/registration-jobs/{id}/live/?since=<seq>

    Latest screenshot of the agent's browser for the live view. Polling this
    is what tells the worker someone is watching. `interactive` is true while
    the job is paused and the user may tap/type in the browser. The image is
    omitted when it hasn't changed since `since`.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "live_view"

    def get(self, request, pk):
        job = _get_owned_job_or_404(request.user, pk)
        live_view.mark_viewer(job.id)
        holding = live_view.is_holding(job.id)
        frame = live_view.get_frame(job.id)
        body = {"state": job.state, "interactive": holding, "frame": None}
        if frame is not None:
            try:
                since = int(request.query_params.get("since", "0"))
            except ValueError:
                since = 0
            body["seq"] = frame["seq"]
            body["interactive"] = holding and bool(frame.get("interactive", True))
            if frame["seq"] != since:
                body["frame"] = {
                    k: frame[k] for k in ("image", "width", "height", "url")
                }
        return Response(body)


class RegistrationJobLiveInputView(APIView):
    """POST /api/registration-jobs/{id}/live/input/ — a tap, typed text, key or scroll."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "live_view"

    def post(self, request, pk):
        job = _get_owned_job_or_404(request.user, pk)
        if not live_view.is_holding(job.id):
            return Response(
                {"detail": "The browser is not waiting for input right now."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = LiveInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        live_view.push_input(job.id, serializer.validated_data)
        return Response(status=status.HTTP_202_ACCEPTED)


class RegistrationJobAnswerView(APIView):
    """
    POST /api/registration-jobs/{id}/questions/{qid}/answer/
    {"answer": "...", "remember": true}  or  {"skip": true}
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, qid):
        from django.shortcuts import get_object_or_404

        from apps.ai_agent.questions import record_answer

        job = _get_owned_job_or_404(request.user, pk)
        question = get_object_or_404(AgentQuestion, id=qid, job=job)
        if question.status != AgentQuestion.Status.PENDING:
            return Response({"detail": "This question has already been handled."}, status=status.HTTP_409_CONFLICT)
        skip = bool(request.data.get("skip"))
        answer = None if skip else str(request.data.get("answer", ""))
        if not skip and not answer.strip():
            return Response({"answer": "Enter an answer, or skip."}, status=status.HTTP_400_BAD_REQUEST)
        if answer and len(answer) > 1000:
            return Response({"answer": "Too long."}, status=status.HTTP_400_BAD_REQUEST)
        record_answer(question, answer, remember=bool(request.data.get("remember", False)))
        return Response(status=status.HTTP_202_ACCEPTED)


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
