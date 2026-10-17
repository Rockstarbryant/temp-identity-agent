"""
The tools other AI clients can call over MCP.

Registering on a site takes minutes, so nothing here blocks: `register_on_site`
starts a job and returns an id, and the client polls `get_job`. Credentials are
deliberately never returned; the requester gets the extracted data, the account
stays in the user's vault.
"""
from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.registration.jobs import create_job
from apps.registration.models import AgentQuestion, RegistrationJob


class ToolError(Exception):
    pass


def _job_for(user, job_id) -> RegistrationJob:
    try:
        return RegistrationJob.objects.select_related("target_website").get(id=job_id, user=user, dismissed_at__isnull=True)
    except (RegistrationJob.DoesNotExist, ValueError, Exception) as exc:  # noqa: BLE001 - bad uuid too
        raise ToolError("No such job.") from exc


def _describe(job: RegistrationJob) -> dict:
    steps = list(job.steps.order_by("-step_index").values_list("detail", flat=True)[:5])
    pending = job.questions.filter(status=AgentQuestion.Status.PENDING).first()
    out = {
        "job_id": str(job.id),
        "site": job.target_website.domain,
        "state": job.state,
        "finished": job.state in RegistrationJob.TERMINAL_STATES,
        "ui_url": f"{settings.FRONTEND_URL}/jobs/{job.id}",
        "recent_steps": [d for d in reversed(steps) if d],
    }
    if job.error_code or job.error_message:
        out["error_code"] = job.error_code
        out["error_message"] = job.error_message
    if job.auth_check:
        out["sign_in_methods"] = job.auth_check
    if pending:
        out["pending_question"] = {"question_id": str(pending.id), "question": pending.question,
                                   "options": pending.options, "sensitive": pending.sensitive}
        out["next"] = "Call answer_question, or ask the user to answer it at ui_url."
    if job.state in RegistrationJob.RESUMABLE_STATES:
        out["next"] = ("A human must complete a step (e.g. a CAPTCHA). Ask the user to open ui_url, "
                       "complete it in the live browser and press continue.")
    if job.state == RegistrationJob.State.COMPLETED:
        out["result"] = job.result or {}
    return out


def register_on_site(user, args: dict) -> dict:
    url = str(args.get("url", "")).strip()
    if not url:
        raise ToolError("url is required.")
    from apps.common.exceptions import UnsafeURLError
    from apps.common.url_safety import validate_url

    try:
        validate_url(url)
    except UnsafeURLError as exc:
        raise ToolError(str(exc)) from exc
    mode = args.get("account_mode")
    if mode not in (None, "temporary", "permanent"):
        raise ToolError("account_mode must be 'temporary' or 'permanent'.")
    try:
        job = create_job(user, url, source=RegistrationJob.Source.MCP, goal=str(args.get("extraction_goal", "")),
                         account_mode=mode, kind=RegistrationJob.Kind.REGISTRATION)
    except ValidationError as exc:
        raise ToolError(_flatten(exc.detail)) from exc
    return {
        **_describe(job),
        "message": ("Started. The agent first checks that the site supports email + password sign-in; if it only "
                    "offers social login the job ends with error_code AUTH_METHOD_UNSUPPORTED. Poll get_job."),
    }


def _flatten(detail) -> str:
    if isinstance(detail, dict):
        return " ".join(_flatten(v) for v in detail.values())
    if isinstance(detail, list):
        return " ".join(_flatten(v) for v in detail)
    return str(detail)


def get_job(user, args: dict) -> dict:
    return _describe(_job_for(user, args.get("job_id")))


def list_jobs(user, args: dict) -> dict:
    limit = min(max(int(args.get("limit", 10) or 10), 1), 25)
    jobs = RegistrationJob.objects.filter(user=user, source="mcp", dismissed_at__isnull=True).select_related("target_website")[:limit]
    return {"jobs": [{"job_id": str(j.id), "site": j.target_website.domain, "state": j.state} for j in jobs]}


def answer_question(user, args: dict) -> dict:
    from apps.ai_agent.questions import record_answer

    job = _job_for(user, args.get("job_id"))
    try:
        q = AgentQuestion.objects.get(id=args.get("question_id"), job=job)
    except (AgentQuestion.DoesNotExist, ValueError, Exception) as exc:  # noqa: BLE001
        raise ToolError("No such question.") from exc
    if q.status != AgentQuestion.Status.PENDING:
        raise ToolError("That question was already handled.")
    answer = str(args.get("answer", "")).strip()
    if not answer:
        raise ToolError("answer is required.")
    record_answer(q, answer[:1000], remember=bool(args.get("remember", False)))
    return {"accepted": True}


def cancel_job(user, args: dict) -> dict:
    from apps.common.exceptions import TempIdentityAgentError
    from apps.registration.orchestration import cancel_registration_job

    job = _job_for(user, args.get("job_id"))
    try:
        job = cancel_registration_job(job.id)
    except TempIdentityAgentError as exc:
        raise ToolError(exc.message) from exc
    return _describe(job)


_STR = {"type": "string"}

TOOLS = [
    {
        "name": "register_on_site",
        "description": (
            "Register an account on a website (using email + password only) and optionally extract information "
            "from it once signed in. Runs in the background: returns a job_id to poll with get_job. If the site "
            "only supports social sign-in (Google, Facebook, ...) the job fails with AUTH_METHOD_UNSUPPORTED "
            "and nothing is created."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {**_STR, "description": "The site's sign-up or home page URL (http/https)."},
                "extraction_goal": {**_STR, "description": "What to read from the site after signing in (optional)."},
                "account_mode": {"type": "string", "enum": ["temporary", "permanent"],
                                 "description": "Defaults to the user's setting. Permanent uses the user's own connected email."},
            },
            "required": ["url"],
        },
        "handler": register_on_site,
    },
    {
        "name": "get_job",
        "description": "Status of a job: state, recent steps, any question waiting for an answer, and the extracted result when finished.",
        "inputSchema": {"type": "object", "properties": {"job_id": _STR}, "required": ["job_id"]},
        "handler": get_job,
    },
    {
        "name": "list_jobs",
        "description": "Your recent jobs started through this MCP endpoint.",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 25}}},
        "handler": list_jobs,
    },
    {
        "name": "answer_question",
        "description": "Answer a question the agent is waiting on (see pending_question in get_job). Only answer with details the user has given you.",
        "inputSchema": {
            "type": "object",
            "properties": {"job_id": _STR, "question_id": _STR, "answer": _STR, "remember": {"type": "boolean"}},
            "required": ["job_id", "question_id", "answer"],
        },
        "handler": answer_question,
    },
    {
        "name": "cancel_job",
        "description": "Cancel a running job.",
        "inputSchema": {"type": "object", "properties": {"job_id": _STR}, "required": ["job_id"]},
        "handler": cancel_job,
    },
]
TOOL_INDEX = {t["name"]: t for t in TOOLS}
