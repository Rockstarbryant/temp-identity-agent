"""
The agent reasoning loop.

Ties everything from Phases 4-7 together: calls the configured AI
provider with the system prompt + available tools, executes whatever
tool calls come back through the validated dispatcher, persists a
RegistrationStep per action (the full audit trail), and stops when the
job reaches a terminal or resumable state — or when MAX_AGENT_STEPS /
MAX_JOB_DURATION_SECONDS is hit, whichever comes first. It never loops
forever: cost control is enforced here, not left to the model's
judgment.
"""
import json
import time

from django.conf import settings
from django.utils import timezone

from ai.router import get_ai_provider
from ai.prompts.system_prompt import SYSTEM_PROMPT
from ai.schemas import ChatMessage
from apps.ai_agent.context import AgentContext
from apps.ai_agent.dispatcher import dispatch_tool_call
from apps.ai_agent.tools import build_tool_definitions
from apps.ai_agent.models import AgentSession
from apps.browser.playwright_client import ManagedBrowserSession
from apps.email_service.models import TemporaryEmail
from apps.registration.models import RegistrationJob, RegistrationStep

_NO_TOOL_CALL_NUDGE = (
    "Reminder: you can only act through your tools. If you're done, call "
    "registration.mark_complete or registration.mark_failed. Otherwise, call "
    "the next tool you need."
)


class AgentRunner:
    """Runs one RegistrationJob's agent loop to completion or a stopping state."""

    def __init__(self, job: RegistrationJob):
        self.job = job
        self.provider = get_ai_provider()
        self.tools = build_tool_definitions()
        self.agent_session, _ = AgentSession.objects.get_or_create(
            job=job, defaults={"provider": self.provider.name, "model": settings.AGENT_ROUTER_MODEL}
        )

    def run(self, target_url: str, resume: bool = False) -> RegistrationJob:
        deadline = time.monotonic() + self.job.timeout_seconds

        if resume:
            instruction = (
                f"Resume registering an account on {target_url}. A human has just "
                f"completed the manual step that was blocking you. Re-inspect the "
                f"current page state before deciding what to do next — do not "
                f"assume the form is in the same state you left it."
            )
        else:
            instruction = (
                f"Register a new temporary account on {target_url}. "
                f"Start by creating an identity, then open the site."
            )

        messages = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=instruction),
        ]

        with ManagedBrowserSession(self.job) as session:
            ctx = AgentContext(job=self.job, session=session)
            if self.job.identity is not None:
                ctx.identity = self.job.identity
                ctx.mailbox = TemporaryEmail.objects.filter(identity=self.job.identity).first()
            step_index = 0

            while step_index < self.job.max_steps:
                if time.monotonic() > deadline:
                    self._fail("Job exceeded its time budget (MAX_JOB_DURATION_SECONDS).")
                    break
                if self.job.state in RegistrationJob.TERMINAL_STATES | RegistrationJob.RESUMABLE_STATES:
                    break

                completion = self.provider.complete(messages, self.tools)
                messages.append(completion.message)
                self._record_usage(completion)

                if not completion.message.tool_calls:
                    messages.append(ChatMessage(role="user", content=_NO_TOOL_CALL_NUDGE))
                    step_index += 1
                    continue

                for tool_call in completion.message.tool_calls:
                    outcome = dispatch_tool_call(ctx, tool_call)
                    self._persist_step(step_index, tool_call, outcome)
                    messages.append(
                        ChatMessage(
                            role="tool", tool_call_id=tool_call.id, content=json.dumps(outcome)
                        )
                    )
                    step_index += 1

                    if self.job.state in RegistrationJob.TERMINAL_STATES | RegistrationJob.RESUMABLE_STATES:
                        break

            else:
                # Loop exhausted max_steps without reaching a stopping state.
                if self.job.state not in RegistrationJob.TERMINAL_STATES | RegistrationJob.RESUMABLE_STATES:
                    self._fail("Reached MAX_AGENT_STEPS without completing registration.")

        self.agent_session.total_steps = step_index
        self.agent_session.save(update_fields=["total_steps", "updated_at"])
        return self.job

    def _persist_step(self, step_index: int, tool_call, outcome: dict) -> None:
        RegistrationStep.objects.create(
            job=self.job,
            step_index=step_index,
            action=tool_call.name,
            tool_name=tool_call.name,
            tool_input=tool_call.arguments,
            tool_result=outcome,
        )

    def _record_usage(self, completion) -> None:
        if completion.input_tokens is not None:
            self.agent_session.total_input_tokens = (
                self.agent_session.total_input_tokens or 0
            ) + completion.input_tokens
        if completion.output_tokens is not None:
            self.agent_session.total_output_tokens = (
                self.agent_session.total_output_tokens or 0
            ) + completion.output_tokens
        self.agent_session.save(
            update_fields=["total_input_tokens", "total_output_tokens", "updated_at"]
        )

    def _fail(self, reason: str) -> None:
        self.job.state = RegistrationJob.State.FAILED
        self.job.error_code = "REGISTRATION_FAILED"
        self.job.error_message = reason
        self.job.completed_at = timezone.now()
        self.job.save(update_fields=["state", "error_code", "error_message", "completed_at", "updated_at"])
