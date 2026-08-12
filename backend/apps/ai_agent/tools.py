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


class RegistrationReasonArgs(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)


# --- Handlers ------------------------------------------------------------------

def _require_session(ctx: AgentContext) -> Any:
    if ctx.session is None:
        raise RegistrationFailedError("No active browser session — call browser.open first.")
    return ctx.session


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
    result = browser_actions.browser_type(_require_session(ctx), args.element_id, args.text)
    return result.model_dump()


def _handle_browser_select(ctx: AgentContext, args: BrowserSelectArgs) -> dict:
    result = browser_actions.browser_select(_require_session(ctx), args.element_id, args.value)
    return result.model_dump()


def _handle_browser_scroll(ctx: AgentContext, args: BrowserScrollArgs) -> dict:
    result = browser_actions.browser_scroll(_require_session(ctx), args.direction)
    return result.model_dump()


def _handle_browser_go_back(ctx: AgentContext, args: NoArgs) -> dict:
    result = browser_actions.browser_go_back(_require_session(ctx))
    return result.model_dump()


def _handle_identity_create(ctx: AgentContext, args: NoArgs) -> dict:
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


def _handle_registration_get_status(ctx: AgentContext, args: NoArgs) -> dict:
    return {"state": ctx.job.state, "steps_taken": ctx.job.steps.count()}


def _handle_registration_mark_complete(ctx: AgentContext, args: NoArgs) -> dict:
    ctx.job.state = RegistrationJob.State.COMPLETED
    ctx.job.completed_at = timezone.now()
    ctx.job.save(update_fields=["state", "completed_at", "updated_at"])

    if ctx.identity is not None:
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


def _handle_registration_mark_captcha_required(ctx: AgentContext, args: RegistrationReasonArgs) -> dict:
    ctx.job.state = RegistrationJob.State.CAPTCHA_REQUIRED
    ctx.job.error_code = "CAPTCHA_REQUIRED"
    ctx.job.error_message = args.reason
    ctx.job.save(update_fields=["state", "error_code", "error_message", "updated_at"])
    return {"state": ctx.job.state}


def _handle_registration_mark_human_action_required(ctx: AgentContext, args: RegistrationReasonArgs) -> dict:
    ctx.job.state = RegistrationJob.State.HUMAN_ACTION_REQUIRED
    ctx.job.error_code = "HUMAN_ACTION_REQUIRED"
    ctx.job.error_message = args.reason
    ctx.job.save(update_fields=["state", "error_code", "error_message", "updated_at"])
    return {"state": ctx.job.state}


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


def build_tool_definitions() -> list[ToolDefinition]:
    """Convert the registry into the provider-agnostic ToolDefinition list."""
    return [
        ToolDefinition(name=spec.name, description=spec.description, parameters=spec.args_model.model_json_schema())
        for spec in TOOL_REGISTRY.values()
    ]
