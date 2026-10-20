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
from django.db.models import Max
from django.utils import timezone

from ai.router import get_ai_provider
from ai.prompts.system_prompt import build_system_prompt
from ai.schemas import ChatMessage, ToolCallRequest
from apps.ai_agent import playbook as playbooks
from apps.ai_agent.context import AgentContext
from apps.ai_agent.dispatcher import dispatch_tool_call
from apps.ai_agent.human_hold import hold_for_human
from apps.ai_agent.tools import build_tool_definitions
from apps.ai_agent.models import AgentSession
from apps.ai_agent.step_detail import describe_step, index_elements, redact_for_storage
from apps.browser import live_view
from apps.profiles import signin
from apps.common.db import ensure_db_connection
from apps.browser.playwright_client import ManagedBrowserSession
from apps.email_service.models import TemporaryEmail
from apps.registration.models import RegistrationJob, RegistrationStep

_NO_TOOL_CALL_NUDGE = (
    "Reminder: you can only act through your tools. If you're done, call "
    "registration.mark_complete or registration.mark_failed. Otherwise, call "
    "the next tool you need."
)


def compress_old_snapshots(messages: list[ChatMessage]) -> None:
    """
    Every browser tool result carries a full page snapshot. Keeping all of them
    makes the prompt balloon on long forms, so only the newest snapshot stays in
    full; earlier ones are reduced to the page URL/title (the agent re-inspects
    before acting anyway).
    """
    indexes: list[int] = []
    for i, m in enumerate(messages):
        if m.role == "tool" and '"snapshot"' in (m.content or ""):
            indexes.append(i)
    for i in indexes[:-1]:
        try:
            data = json.loads(messages[i].content)
            snap = (data.get("result") or {}).get("snapshot")
            if not isinstance(snap, dict) or isinstance(snap.get("elements"), str):
                continue
            data["result"]["snapshot"] = {
                "url": snap.get("url", ""), "title": snap.get("title", ""),
                "elements": "[omitted: superseded by a newer snapshot — inspect again if you need it]",
            }
            messages[i] = messages[i].model_copy(update={"content": json.dumps(data)})
        except (ValueError, AttributeError, TypeError):
            continue


class AgentRunner:
    """Runs one RegistrationJob's agent loop to completion or a stopping state."""

    def __init__(self, job: RegistrationJob):
        self.job = job
        self.provider = get_ai_provider()
        self.tools = build_tool_definitions()
        self._frames = live_view.FramePublisher(job.id)
        ensure_db_connection()
        self.agent_session, _ = AgentSession.objects.get_or_create(
            job=job, defaults={"provider": self.provider.name, "model": (self.provider.model or "")[:100]}
        )

    def run(self, target_url: str, resume: bool = False) -> RegistrationJob:
        deadline = time.monotonic() + self.job.timeout_seconds

        if self.job.kind == RegistrationJob.Kind.FORM and not resume:
            instruction = f"Fill in and submit the form at {target_url}."
        elif resume:
            instruction = (
                f"Resume registering an account on {target_url}. A human has just "
                f"completed the manual step that was blocking you. Re-inspect the "
                f"current page state before deciding what to do next — do not "
                f"assume the form is in the same state you left it."
            )
        else:
            instruction = (
                f"Register a new {'permanent' if self.job.account_mode == 'permanent' else 'temporary'} "
                f"account on {target_url}. Start by creating an identity, then open the site."
            )

        messages = [
            ChatMessage(role="system", content=build_system_prompt(self.job)),
            ChatMessage(role="user", content=instruction),
        ]

        # Forms behind a Google/Microsoft sign-in reuse the user's connected account session.
        # It is loaded only from this job owner's own account row, into this job's own browser.
        provider = signin.provider_for_url(target_url) if self.job.kind == RegistrationJob.Kind.FORM else ""
        account = signin.get_account(self.job.user, provider)
        with ManagedBrowserSession(self.job, storage_state=account.get_session() if account else None) as session:
            ctx = AgentContext(job=self.job, session=session, provider=provider)
            if self.job.identity is not None:
                ctx.identity = self.job.identity
                ctx.mailbox = TemporaryEmail.objects.filter(identity=self.job.identity).first()
            # A resumed job already has steps 0..n from the earlier run; continue
            # numbering after them (job+step_index is unique). The browser itself
            # is a fresh one, so the agent re-inspects the page first.
            last_index = self.job.steps.aggregate(m=Max("step_index"))["m"]
            step_index = 0 if last_index is None else last_index + 1
            elements: dict[str, dict] = {}
            step_budget = step_index + self.job.max_steps

            # Sites the agent has signed up on before: replay the saved steps in code, then let the
            # AI take over for the part that differs every time (the verification email).
            recorder = playbooks.PlaybookRecorder(domain=self.job.target_website.domain)
            used_playbook = None
            replay_ok = False
            track_playbook = self.job.kind == RegistrationJob.Kind.REGISTRATION and not resume
            if track_playbook:
                used_playbook = playbooks.find_playbook(self.job.target_website.domain)
                if used_playbook is not None:
                    step_index, elements, replay_ok, note = self._replay_playbook(
                        ctx, session, used_playbook, recorder, step_index, elements)
                    messages.append(ChatMessage(role="user", content=note))
                    step_budget = max(step_budget, step_index + self.job.max_steps)

            while step_index < step_budget:
                if time.monotonic() > deadline:
                    self._fail("Job exceeded its time budget (MAX_JOB_DURATION_SECONDS).")
                    break
                if self.job.state in RegistrationJob.TERMINAL_STATES | RegistrationJob.RESUMABLE_STATES:
                    break

                compress_old_snapshots(messages)
                completion = self.provider.complete(messages, self.tools)
                ensure_db_connection()  # the LLM call can outlast the DB's idle timeout
                messages.append(completion.message)
                self._record_usage(completion)

                if not completion.message.tool_calls:
                    messages.append(ChatMessage(role="user", content=_NO_TOOL_CALL_NUDGE))
                    step_index += 1
                    continue

                answered: set[str] = set()
                resumed_by_human = False
                for tool_call in completion.message.tool_calls:
                    # Look the element up *before* the call: a click changes the page.
                    element = elements.get(str(tool_call.arguments.get("element_id", "")))
                    outcome = dispatch_tool_call(ctx, tool_call)
                    ensure_db_connection()  # page loads / mailbox waits are slow too
                    self._persist_step(step_index, tool_call, outcome, element)
                    if track_playbook:
                        recorder.observe(ctx, tool_call.name, tool_call.arguments, element, outcome)
                    if outcome.get("success"):
                        fresh = index_elements(outcome)
                        if fresh:
                            elements = fresh
                    messages.append(
                        ChatMessage(
                            role="tool", tool_call_id=tool_call.id, content=json.dumps(outcome)
                        )
                    )
                    answered.add(tool_call.id)
                    step_index += 1
                    if tool_call.name == "user.ask":
                        # Time spent waiting for the user doesn't count against the job's budget.
                        deadline = time.monotonic() + self.job.timeout_seconds
                    self._publish_frame(session)

                    if self.job.state in RegistrationJob.RESUMABLE_STATES:
                        # Keep the browser open so the user can finish the step
                        # (CAPTCHA etc.) from the live view and continue right here.
                        resumed_by_human = self._hold_for_human(session, deadline)
                        if resumed_by_human and ctx.awaiting_signin:
                            ctx.awaiting_signin = False
                            if account and not signin.is_login_url(provider, session.page.url):
                                ctx.signed_in = True
                                signin.save_session(account, session)
                        if resumed_by_human:
                            # Extend the budget by the time the human took.
                            deadline = time.monotonic() + self.job.timeout_seconds
                        break
                    if self.job.state in RegistrationJob.TERMINAL_STATES:
                        break

                if resumed_by_human:
                    for tc in completion.message.tool_calls:
                        if tc.id not in answered:
                            messages.append(
                                ChatMessage(
                                    role="tool", tool_call_id=tc.id,
                                    content=json.dumps({"success": False, "error": "Skipped: the job was paused."}),
                                )
                            )
                    messages.append(
                        ChatMessage(
                            role="user",
                            content=(
                                "A human has just completed the manual step in this same browser "
                                "window. Call browser.inspect to see the current page, then continue."
                            ),
                        )
                    )

            else:
                # Loop exhausted max_steps without reaching a stopping state.
                if self.job.state not in RegistrationJob.TERMINAL_STATES | RegistrationJob.RESUMABLE_STATES:
                    self._fail("Reached MAX_AGENT_STEPS without completing registration.")

        self.agent_session.total_steps = step_index
        self.agent_session.save(update_fields=["total_steps", "updated_at"])
        if self.job.state == RegistrationJob.State.COMPLETED:
            ensure_db_connection()
            from apps.accounts.service import ensure_vault_account

            ensure_vault_account(self.job)  # safety net: a finished sign-up always lands in the vault
        if track_playbook:
            ensure_db_connection()
            playbooks.finalize(self.job, recorder, used_playbook, replay_ok)
        return self.job

    def _replay_playbook(self, ctx, session, playbook, recorder, step_index: int, elements: dict):
        """
        Run a site's saved steps with no AI calls. Returns (step_index, elements, ok, note) where
        `note` is the message that tells the AI where things stand.
        """
        domain = self.job.target_website.domain
        steps = playbook.steps
        total = len(steps)
        done = 0
        state = {"index": step_index, "elements": elements}

        def run(name: str, args: dict) -> dict:
            call = ToolCallRequest(id=f"playbook-{state['index']}", name=name, arguments=args)
            element = state["elements"].get(str(args.get("element_id", "")))
            outcome = dispatch_tool_call(ctx, call)
            ensure_db_connection()
            self._persist_step(state["index"], call, outcome, element)
            recorder.observe(ctx, name, args, element, outcome)
            if outcome.get("success"):
                fresh = index_elements(outcome)
                if fresh:
                    state["elements"] = fresh
            state["index"] += 1
            self._publish_frame(session)
            return outcome

        RegistrationStep.objects.create(
            job=self.job, step_index=state["index"], action="playbook.replay", tool_name="playbook.replay",
            tool_result={"success": True, "steps": total},
            detail=f"Using the steps saved for {domain} ({total} steps), no AI needed for this part",
        )
        state["index"] += 1

        def stop(reason: str) -> tuple:
            note = (
                f"Saved steps for {domain} were replayed for {done} of {total} steps and then stopped: {reason}. "
                "What was done so far is real. A temporary identity already exists (use identity.get if you need it). "
                "Call browser.inspect to see the page as it is now, then carry on yourself without redoing finished fields."
            )
            return state["index"], state["elements"], False, note

        if self.job.source == RegistrationJob.Source.MCP and not self.job.auth_check:
            self.job.auth_check = playbook.auth_check or {"email_password": True, "methods": ["email_password"],
                                                          "notes": "known from saved steps"}
            self.job.save(update_fields=["auth_check", "updated_at"])

        if run("identity.create", {}).get("success") is not True:
            return stop("the temporary identity could not be created")
        from apps.ai_agent.tools import _profile_values

        values = playbooks.value_sources(ctx.identity, _profile_values(self.job.user))

        for step in steps:
            op = step.get("op")
            if op == "open":
                if not playbooks.same_site(step.get("url", ""), domain):
                    return stop("the saved start page is no longer on this site")
                if not run("browser.open", {"url": step["url"]}).get("success"):
                    return stop("the page could not be opened")
                done += 1
                continue

            target = step.get("target") or {}
            label = target.get("label") or target.get("name") or "a field"
            el = playbooks.find_element(list(state["elements"].values()), target)
            if el is None:
                run("browser.inspect", {})
                el = playbooks.find_element(list(state["elements"].values()), target)
            if el is None:
                return stop(f"“{label}” was not found on the page (the site may have changed)")

            if op == "check" and el.get("checked"):
                done += 1
                continue
            if op == "fill":
                value = values.get(step.get("source", ""))
                if value is None:
                    return stop(f"“{label}” needs a detail that is not saved ({step.get('source')})")
                tool, args = "browser.type", {"element_id": el["element_id"], "text": value}
            elif op == "select":
                value = values.get(step["source"]) if step.get("source") else step.get("value")
                if value is None:
                    return stop(f"“{label}” needs a detail that is not saved ({step.get('source')})")
                tool, args = "browser.select", {"element_id": el["element_id"], "value": value}
            elif op in ("click", "check"):
                tool, args = "browser.click", {"element_id": el["element_id"]}
            else:
                return stop(f"an unknown saved step ({op})")

            if not run(tool, args).get("success"):
                run("browser.inspect", {})  # one retry on a fresh snapshot
                el = playbooks.find_element(list(state["elements"].values()), target)
                if el is None:
                    return stop(f"“{label}” could not be used")
                args["element_id"] = el["element_id"]
                if not run(tool, args).get("success"):
                    return stop(f"“{label}” could not be used")
            done += 1

        note = (
            f"Saved steps for {domain} were replayed ({total} steps): a temporary identity was created, the sign-up "
            f"form was filled with its details and submitted. Do NOT fill the form again. Call browser.read_text to see "
            "what the page says now, then continue with the verification step (email.wait_for_verification) as usual."
        )
        return state["index"], state["elements"], True, note

    def _publish_frame(self, session) -> None:
        """Share a screenshot for the live view, but only while someone is watching."""
        try:
            if live_view.has_viewer(self.job.id):
                self._frames.publish(session.page)
        except Exception:  # noqa: BLE001 - a failed preview must never break the job
            pass

    def _hold_for_human(self, session, deadline: float) -> bool:
        """Pause for the user (CAPTCHA, sign-in...) with the live view; see human_hold."""
        return hold_for_human(self.job, session, self._frames)

    def _persist_step(self, step_index: int, tool_call, outcome: dict, element: dict | None = None) -> None:
        safe_input, safe_outcome = redact_for_storage(
            tool_call.name, tool_call.arguments, element, outcome
        )
        RegistrationStep.objects.create(
            job=self.job,
            step_index=step_index,
            action=tool_call.name,
            tool_name=tool_call.name,
            tool_input=safe_input,
            tool_result=safe_outcome,
            detail=describe_step(tool_call.name, tool_call.arguments, element, outcome),
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
        update_fields = ["total_input_tokens", "total_output_tokens", "updated_at"]
        # With the fallback chain / a router model, the provider and concrete
        # model that answered can change mid-job; keep the session row accurate.
        if completion.provider and completion.provider != self.agent_session.provider:
            self.agent_session.provider = completion.provider
            update_fields.append("provider")
        if completion.model and completion.model[:100] != self.agent_session.model:
            self.agent_session.model = completion.model[:100]
            update_fields.append("model")
        self.agent_session.save(update_fields=update_fields)

    def _fail(self, reason: str) -> None:
        self.job.state = RegistrationJob.State.FAILED
        self.job.error_code = "REGISTRATION_FAILED"
        self.job.error_message = reason
        self.job.completed_at = timezone.now()
        self.job.save(update_fields=["state", "error_code", "error_message", "completed_at", "updated_at"])
