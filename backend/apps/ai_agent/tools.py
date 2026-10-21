"""
The AI agent's complete tool surface.

Every tool the model can call is registered here with a Pydantic
argument schema (validated before execution — malformed tool calls
never reach the underlying service functions) and a handler wired to
the real Phase 4/5/6 service code — not a separate reimplementation.

This IS the allowlist. If a tool isn't in TOOL_REGISTRY, the agent has
no way to invoke it, structurally — there is no fallback "call anything
the model names" path.
"""
from dataclasses import dataclass
from typing import Any, Callable, Literal

from django.utils import timezone
from pydantic import BaseModel, Field

from ai.schemas import ToolDefinition
from apps.ai_agent.context import AgentContext
from apps.browser import actions as browser_actions
from apps.ai_agent import questions
from apps.browser.page_inspector import inspect_page
from apps.common.exceptions import RegistrationFailedError
from apps.email_service import service as email_service
from apps.identities import service as identity_service
from apps.registration.models import RegistrationJob


# --- Argument schemas ---------------------------------------------------------

class NoArgs(BaseModel):
    pass


class BrowserOpenArgs(BaseModel):
    url: str = Field(..., description="The URL to navigate to.")


class BrowserClickArgs(BaseModel):
    element_id: str = Field(..., description="element_id from the most recent inspect/open result.")


class BrowserTypeArgs(BaseModel):
    element_id: str = Field(..., description="element_id from the most recent inspect/open result.")
    text: str = Field(..., description="Text to type into the field.")


class BrowserSelectArgs(BaseModel):
    element_id: str
    value: str = Field(..., description="The option value to select.")


class BrowserScrollArgs(BaseModel):
    direction: Literal["up", "down"] = "down"


class EmailReadMessageArgs(BaseModel):
    external_id: str


class EmailWaitForVerificationArgs(BaseModel):
    timeout_seconds: int = Field(default=60, ge=1, le=300)


class ProfileGetArgs(BaseModel):
    keys: list[str] = Field(
        default_factory=list,
        description="Detail keys to fetch, e.g. ['phone', 'county']. Omit to see which details are saved (names only, no values).",
    )


class UserAskArgs(BaseModel):
    question: str = Field(..., min_length=3, max_length=500, description="A clear, specific question for the user.")
    field_key: str = Field(
        default="",
        max_length=60,
        description="snake_case name for this detail (e.g. 'phone', 'home_county') so it can be saved and reused. Reuse standard keys when they fit.",
    )
    options: list[str] = Field(default_factory=list, description="If the form offers fixed choices, list them.")
    sensitive: bool = Field(default=False, description="True for IDs or similar; the answer is then not shown in the job timeline.")


class AuthMethodsArgs(BaseModel):
    email_password: bool = Field(..., description="True only if the site lets you sign up / log in with an email address and password.")
    methods: list[str] = Field(default_factory=list, description="Everything offered, e.g. ['email_password', 'google', 'facebook'].")
    notes: str = Field(default="", max_length=500)


class FormAnswer(BaseModel):
    question: str = Field(..., max_length=300)
    answer: str = Field(..., max_length=1000)


class FormCompleteArgs(BaseModel):
    submitted: list[FormAnswer] = Field(..., min_length=1, description="Every question and the answer you submitted.")
    note: str = Field(default="", max_length=500, description="Anything the user should know (e.g. the confirmation message).")


class DataResultArgs(BaseModel):
    summary: str = Field(..., min_length=1, max_length=1000, description="One or two sentences on what was found.")
    data: dict[str, Any] = Field(default_factory=dict, description="The extracted information as key/value pairs.")


class RegistrationReasonArgs(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)


# --- Handlers ------------------------------------------------------------------

def _require_session(ctx: AgentContext) -> Any:
    if ctx.session is None:
        raise RegistrationFailedError("No active browser session — call browser.open first.")
    return ctx.session


def _require_auth_check(ctx: AgentContext) -> None:
    """MCP jobs must establish that the site supports email+password sign-in before anything is filled in."""
    job = ctx.job
    if job.source == RegistrationJob.Source.MCP and job.kind == RegistrationJob.Kind.REGISTRATION and not job.auth_check:
        raise RegistrationFailedError(
            "Before registering, find out how this site lets people sign up or log in, then call "
            "site.report_auth_methods. Do not fill in any form until you have."
        )


def _handle_browser_open(ctx: AgentContext, args: BrowserOpenArgs) -> dict:
    result = browser_actions.browser_open(_require_session(ctx), args.url)
    return result.model_dump()


def _handle_browser_inspect(ctx: AgentContext, args: NoArgs) -> dict:
    result = browser_actions.browser_inspect(_require_session(ctx))
    return result.model_dump()


def _handle_browser_click(ctx: AgentContext, args: BrowserClickArgs) -> dict:
    result = browser_actions.browser_click(_require_session(ctx), args.element_id)
    return result.model_dump()


def _handle_browser_type(ctx: AgentContext, args: BrowserTypeArgs) -> dict:
    _require_auth_check(ctx)
    result = browser_actions.browser_type(_require_session(ctx), args.element_id, args.text)
    return result.model_dump()


def _handle_browser_select(ctx: AgentContext, args: BrowserSelectArgs) -> dict:
    _require_auth_check(ctx)
    result = browser_actions.browser_select(_require_session(ctx), args.element_id, args.value)
    return result.model_dump()


def _handle_browser_scroll(ctx: AgentContext, args: BrowserScrollArgs) -> dict:
    result = browser_actions.browser_scroll(_require_session(ctx), args.direction)
    return result.model_dump()


def _handle_browser_go_back(ctx: AgentContext, args: NoArgs) -> dict:
    result = browser_actions.browser_go_back(_require_session(ctx))
    return result.model_dump()


def _profile_values(user) -> dict[str, str]:
    from apps.profiles.models import ProfileEntry

    return {e.key: e.get_value() for e in ProfileEntry.objects.filter(user=user)}


def _handle_identity_create(ctx: AgentContext, args: NoArgs) -> dict:
    _require_auth_check(ctx)
    if ctx.job.kind == RegistrationJob.Kind.ACCOUNT_TASK:
        raise RegistrationFailedError("This account already exists. Call identity.get for its sign-in details; do not create a new identity.")
    if ctx.job.kind == RegistrationJob.Kind.FORM:
        raise RegistrationFailedError("This job fills in a form; it doesn't create an account. Use profile.get and user.ask instead.")

    if ctx.job.account_mode == RegistrationJob.AccountMode.PERMANENT:
        from apps.profiles.models import EmailConnection

        connection = EmailConnection.objects.filter(user=ctx.job.user).first()
        if connection is None:
            raise RegistrationFailedError(
                "This is a permanent-account job but no email is connected. Call registration.mark_human_action_required "
                "asking the user to connect their email in Settings."
            )
        identity = identity_service.create_permanent_identity(ctx.job.user, _profile_values(ctx.job.user))
        ctx.job.identity = identity
        ctx.job.save(update_fields=["identity", "updated_at"])
        mailbox = email_service.attach_user_mailbox(identity, connection)
        ctx.identity = identity
        ctx.mailbox = mailbox
        return {"id": str(identity.id), "name": identity.name, "username": identity.username,
                "email": identity.email, "permanent": True}

    identity = identity_service.create_temporary_identity(ctx.job.user)
    ctx.job.identity = identity
    ctx.job.save(update_fields=["identity", "updated_at"])
    mailbox = email_service.create_mailbox_for_identity(identity)
    ctx.identity = identity
    ctx.mailbox = mailbox
    return {"id": str(identity.id), "name": identity.name, "username": identity.username, "email": identity.email}


def _handle_identity_get(ctx: AgentContext, args: NoArgs) -> dict:
    if ctx.identity is None:
        raise RegistrationFailedError("No identity created yet — call identity.create first.")
    return {
        "id": str(ctx.identity.id), "name": ctx.identity.name,
        "username": ctx.identity.username, "email": ctx.identity.email,
        "password": ctx.identity.get_password(),
    }


def _handle_email_get_mailbox(ctx: AgentContext, args: NoArgs) -> dict:
    if ctx.mailbox is None:
        raise RegistrationFailedError("No mailbox provisioned yet — call identity.create first.")
    return {"address": ctx.mailbox.address, "provider": ctx.mailbox.provider, "status": ctx.mailbox.status}


def _handle_email_list_messages(ctx: AgentContext, args: NoArgs) -> dict:
    if ctx.mailbox is None:
        raise RegistrationFailedError("No mailbox provisioned yet.")
    messages = email_service.sync_messages(ctx.mailbox)
    return {"messages": [
        {"external_id": m.external_id, "sender": m.sender, "subject": m.subject} for m in messages
    ]}


def _handle_email_read_message(ctx: AgentContext, args: EmailReadMessageArgs) -> dict:
    if ctx.mailbox is None:
        raise RegistrationFailedError("No mailbox provisioned yet.")
    from apps.email_service.models import EmailMessage

    try:
        message = EmailMessage.objects.get(mailbox=ctx.mailbox, external_id=args.external_id)
    except EmailMessage.DoesNotExist as exc:
        raise RegistrationFailedError(f"No message with id {args.external_id!r} in mailbox.") from exc
    return {
        "subject": message.subject, "sender": message.sender,
        "text_body": message.text_body[:5000],  # cap to keep tool results bounded
        "extracted_link": message.extracted_link, "extracted_otp": message.extracted_otp,
    }


def _handle_email_wait_for_verification(ctx: AgentContext, args: EmailWaitForVerificationArgs) -> dict:
    if ctx.mailbox is None:
        raise RegistrationFailedError("No mailbox provisioned yet.")
    message = email_service.wait_for_verification_email(ctx.mailbox, timeout_seconds=args.timeout_seconds)
    if message is None:
        return {"received": False}
    return {
        "received": True, "subject": message.subject,
        "extracted_link": message.extracted_link, "extracted_otp": message.extracted_otp,
    }


def _handle_browser_read_text(ctx: AgentContext, args: NoArgs) -> dict:
    page = _require_session(ctx).page
    text = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
    return {"url": page.url, "title": page.title(), "text": text[:8000], "truncated": len(text) > 8000}


def _handle_profile_get(ctx: AgentContext, args: ProfileGetArgs) -> dict:
    from apps.profiles.models import ProfileEntry

    entries = {e.key: e for e in ProfileEntry.objects.filter(user=ctx.job.user)}
    if not args.keys:
        return {"saved_details": [{"key": k, "label": e.label} for k, e in entries.items()]}
    found = {k: entries[k].get_value() for k in args.keys if k in entries}
    missing = [k for k in args.keys if k not in entries]
    return {"values": found, "not_saved": missing}


def _handle_user_ask(ctx: AgentContext, args: UserAskArgs) -> dict:
    return questions.ask_user(ctx.job, args.question, key=args.field_key, options=args.options, sensitive=args.sensitive)


def _handle_site_report_auth_methods(ctx: AgentContext, args: AuthMethodsArgs) -> dict:
    ctx.job.auth_check = {"email_password": args.email_password, "methods": args.methods[:10], "notes": args.notes}
    if args.email_password:
        ctx.job.save(update_fields=["auth_check", "updated_at"])
        return {"proceed": True}
    social = ", ".join(m for m in args.methods if m != "email_password") or "social sign-in only"
    ctx.job.state = RegistrationJob.State.FAILED
    ctx.job.error_code = "AUTH_METHOD_UNSUPPORTED"
    ctx.job.error_message = (
        f"This site doesn't offer sign-up or login with an email and password ({social}). "
        "This service can only register with email and password, so it can't use social sign-in."
    )
    ctx.job.completed_at = timezone.now()
    ctx.job.save(update_fields=["auth_check", "state", "error_code", "error_message", "completed_at", "updated_at"])
    return {"proceed": False, "reason": ctx.job.error_message}


def _handle_form_complete(ctx: AgentContext, args: FormCompleteArgs) -> dict:
    if ctx.job.kind != RegistrationJob.Kind.FORM:
        raise RegistrationFailedError(
            "form.complete is only for form-filling jobs. This job creates an account: finish it with "
            "registration.mark_complete once the account is created and verified."
        )
    ctx.job.result = {"submitted": [a.model_dump() for a in args.submitted], "note": args.note}
    ctx.job.state = RegistrationJob.State.COMPLETED
    ctx.job.completed_at = timezone.now()
    ctx.job.save(update_fields=["result", "state", "completed_at", "updated_at"])
    return {"state": ctx.job.state}


def _handle_data_submit_result(ctx: AgentContext, args: DataResultArgs) -> dict:
    import json

    if len(json.dumps(args.data, default=str)) > 20000:
        raise RegistrationFailedError("The data is too large (20,000 characters max). Summarize it.")
    ctx.job.result = {"summary": args.summary, "data": args.data}
    ctx.job.save(update_fields=["result", "updated_at"])
    return {"saved": True}


def _handle_registration_get_status(ctx: AgentContext, args: NoArgs) -> dict:
    return {"state": ctx.job.state, "steps_taken": ctx.job.steps.count()}


def _handle_registration_mark_complete(ctx: AgentContext, args: NoArgs) -> dict:
    if ctx.job.goal and not ctx.job.result:
        raise RegistrationFailedError(
            "The user asked you to extract information. Call data.submit_result with it before marking the job complete."
        )
    if ctx.job.kind == RegistrationJob.Kind.FORM and not ctx.job.result:
        raise RegistrationFailedError("Call form.complete with the questions and answers you submitted.")
    ctx.job.state = RegistrationJob.State.COMPLETED
    ctx.job.completed_at = timezone.now()
    ctx.job.save(update_fields=["state", "completed_at", "updated_at"])

    if ctx.identity is not None and ctx.job.kind != RegistrationJob.Kind.ACCOUNT_TASK:
        from apps.accounts.models import TemporaryAccount

        TemporaryAccount.objects.get_or_create(
            job=ctx.job,
            defaults={"identity": ctx.identity, "website": ctx.job.target_website},
        )

    return {"state": ctx.job.state}


def _handle_registration_mark_failed(ctx: AgentContext, args: RegistrationReasonArgs) -> dict:
    ctx.job.state = RegistrationJob.State.FAILED
    ctx.job.error_code = "REGISTRATION_FAILED"
    ctx.job.error_message = args.reason
    ctx.job.completed_at = timezone.now()
    ctx.job.save(update_fields=["state", "error_code", "error_message", "completed_at", "updated_at"])
    return {"state": ctx.job.state}


def _capture_manual_kit(ctx: AgentContext) -> None:
    if ctx.job.kind == RegistrationJob.Kind.REGISTRATION and ctx.identity is not None:
        from apps.registration.manual import snapshot_into_job

        snapshot_into_job(ctx)


def _handle_registration_mark_captcha_required(ctx: AgentContext, args: RegistrationReasonArgs) -> dict:
    ctx.job.state = RegistrationJob.State.CAPTCHA_REQUIRED
    ctx.job.error_code = "CAPTCHA_REQUIRED"
    ctx.job.error_message = args.reason
    ctx.job.save(update_fields=["state", "error_code", "error_message", "updated_at"])
    _capture_manual_kit(ctx)
    return {"state": ctx.job.state}


def _handle_registration_mark_human_action_required(ctx: AgentContext, args: RegistrationReasonArgs) -> dict:
    ctx.job.state = RegistrationJob.State.HUMAN_ACTION_REQUIRED
    ctx.job.error_code = "HUMAN_ACTION_REQUIRED"
    ctx.job.error_message = args.reason
    ctx.job.save(update_fields=["state", "error_code", "error_message", "updated_at"])
    _capture_manual_kit(ctx)
    return {"state": ctx.job.state}


def _pause_for_signin(ctx: AgentContext, provider: str, reason: str) -> dict:
    """Hand the browser to the user (live view) so they can sign in themselves."""
    ctx.awaiting_signin = True
    ctx.job.state = RegistrationJob.State.HUMAN_ACTION_REQUIRED
    ctx.job.error_code = "HUMAN_ACTION_REQUIRED"
    ctx.job.error_message = reason
    ctx.job.save(update_fields=["state", "error_code", "error_message", "updated_at"])
    return {"success": False, "paused_for_human": True, "message": reason}


def _handle_account_sign_in(ctx: AgentContext, args: NoArgs) -> dict:
    from apps.profiles import signin

    page = ctx.session.page
    provider = signin.provider_for_url(page.url) or signin.provider_for_url(ctx.job.target_url)
    if not provider:
        return {"success": False, "error": "This is not a Google or Microsoft sign-in page; this tool does not apply."}
    ctx.provider = provider
    name = "Google" if provider == "google" else "Microsoft"
    if not signin.is_login_url(provider, page.url):
        return {"success": True, "signed_in": True, "note": "No sign-in page is showing; carry on with the form."}

    account = signin.get_account(ctx.job.user, provider)
    if account is None:
        return _pause_for_signin(
            ctx, provider,
            f"This form needs a {name} sign-in. Sign in in the browser below, then press continue. "
            f"(Connect a {name} account in Settings and the agent can do this itself next time.)",
        )
    result = signin.perform_login(page, account)
    if result.ok:
        ctx.signed_in = True
        signin.save_session(account, ctx.session)
        return {"success": True, "signed_in": True, "note": "Signed in. Re-inspect the page and continue."}
    account.last_error = result.reason[:300]
    account.save(update_fields=["last_error", "updated_at"])
    return _pause_for_signin(ctx, provider, result.reason)


# --- Registry ------------------------------------------------------------------

@dataclass
class ToolSpec:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[AgentContext, BaseModel], dict]


TOOL_REGISTRY: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in [
        ToolSpec("browser.open", "Navigate the browser to a URL.", BrowserOpenArgs, _handle_browser_open),
        ToolSpec("browser.inspect", "Get the current page's structured interactive elements.", NoArgs, _handle_browser_inspect),
        ToolSpec("browser.click", "Click an element by its element_id.", BrowserClickArgs, _handle_browser_click),
        ToolSpec("browser.type", "Type text into an input by its element_id.", BrowserTypeArgs, _handle_browser_type),
        ToolSpec("browser.select", "Select an option in a <select> by its element_id.", BrowserSelectArgs, _handle_browser_select),
        ToolSpec("browser.scroll", "Scroll the page up or down.", BrowserScrollArgs, _handle_browser_scroll),
        ToolSpec("browser.go_back", "Navigate back to the previous page.", NoArgs, _handle_browser_go_back),
        ToolSpec("browser.read_text", "Read the visible text of the current page (questions, descriptions, results).", NoArgs, _handle_browser_read_text),
        ToolSpec("profile.get", "See which details the user has saved (no keys), or fetch values for specific keys.", ProfileGetArgs, _handle_profile_get),
        ToolSpec("user.ask", "Ask the user for a detail you don't have. Waits for their answer. Never invent personal data; ask.", UserAskArgs, _handle_user_ask),
        ToolSpec("account.sign_in", "Sign in to the Google/Microsoft account the user connected, when the form shows a Google or Microsoft sign-in page. You never see the password. If it needs the user, the job pauses for them automatically.", NoArgs, _handle_account_sign_in),
        ToolSpec("site.report_auth_methods", "Report whether the site supports sign-up/login with email and password.", AuthMethodsArgs, _handle_site_report_auth_methods),
        ToolSpec("form.complete", "After submitting a form: report every question and answer, and finish the job.", FormCompleteArgs, _handle_form_complete),
        ToolSpec("data.submit_result", "Save the information you extracted for the requester.", DataResultArgs, _handle_data_submit_result),
        ToolSpec("identity.create", "Generate a new temporary identity and mailbox for this job.", NoArgs, _handle_identity_create),
        ToolSpec("identity.get", "Get the current job's temporary identity, including its password.", NoArgs, _handle_identity_get),
        ToolSpec("email.get_mailbox", "Get the current job's temporary mailbox address.", NoArgs, _handle_email_get_mailbox),
        ToolSpec("email.list_messages", "List messages currently in the mailbox.", NoArgs, _handle_email_list_messages),
        ToolSpec("email.read_message", "Read one message's full content by external_id.", EmailReadMessageArgs, _handle_email_read_message),
        ToolSpec("email.wait_for_verification", "Block until a new message arrives (or timeout).", EmailWaitForVerificationArgs, _handle_email_wait_for_verification),
        ToolSpec("registration.get_status", "Get the current job's state.", NoArgs, _handle_registration_get_status),
        ToolSpec("registration.mark_complete", "Mark the job as successfully completed.", NoArgs, _handle_registration_mark_complete),
        ToolSpec("registration.mark_failed", "Mark the job as failed, with a reason.", RegistrationReasonArgs, _handle_registration_mark_failed),
        ToolSpec("registration.mark_captcha_required", "Pause the job: a CAPTCHA needs a human.", RegistrationReasonArgs, _handle_registration_mark_captcha_required),
        ToolSpec("registration.mark_human_action_required", "Pause the job: some other manual step is needed.", RegistrationReasonArgs, _handle_registration_mark_human_action_required),
    ]
}


def _tolerant_schema(model: type[BaseModel]) -> dict:
    """JSON schema where optional arguments may also be null.

    Models often send `"options": null` for an argument they have nothing for.
    Some providers (Groq) validate that against the schema server-side and reject the
    whole request with a 400, so optional properties must explicitly allow null. The
    dispatcher drops null arguments before validating, so defaults still apply.
    """
    schema = model.model_json_schema()
    required = set(schema.get("required", []))
    for name, prop in schema.get("properties", {}).items():
        if name in required or not isinstance(prop, dict):
            continue
        if "type" in prop and isinstance(prop["type"], str):
            prop["type"] = [prop["type"], "null"]
        elif "anyOf" in prop:
            if not any(o.get("type") == "null" for o in prop["anyOf"] if isinstance(o, dict)):
                prop["anyOf"].append({"type": "null"})
        else:
            schema["properties"][name] = {"anyOf": [prop, {"type": "null"}]}
    return schema


def build_tool_definitions() -> list[ToolDefinition]:
    """Convert the registry into the provider-agnostic ToolDefinition list."""
    return [
        ToolDefinition(name=spec.name, description=spec.description, parameters=_tolerant_schema(spec.args_model))
        for spec in TOOL_REGISTRY.values()
    ]
