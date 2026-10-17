"""
Validates and executes one tool call.

This is the chokepoint the AI security requirement depends on: every
tool call's arguments are validated against its Pydantic schema before
the handler ever runs. A malformed call (wrong types, missing required
fields, an unknown tool name) never reaches application code — it comes
back as a structured error the model can see and correct, not a crash.
"""
from pydantic import ValidationError

from ai.schemas import ToolCallRequest
from apps.ai_agent.context import AgentContext
from apps.ai_agent.tools import TOOL_REGISTRY
from apps.common.exceptions import TempIdentityAgentError


def dispatch_tool_call(ctx: AgentContext, tool_call: ToolCallRequest) -> dict:
    spec = TOOL_REGISTRY.get(tool_call.name)
    if spec is None:
        return {"success": False, "error": f"Unknown tool {tool_call.name!r}. Not in the allowlist."}

    try:
        args = spec.args_model(**{k: v for k, v in (tool_call.arguments or {}).items() if v is not None})
    except ValidationError as exc:
        return {"success": False, "error": f"Invalid arguments for {tool_call.name}: {exc}"}

    try:
        result = spec.handler(ctx, args)
    except TempIdentityAgentError as exc:
        return {"success": False, "error": f"{exc.code}: {exc.message}"}
    except Exception as exc:  # noqa: BLE001 — deliberately broad: never let a tool crash the agent loop
        return {"success": False, "error": f"Unexpected error in {tool_call.name}: {exc}"}

    return {"success": True, "result": result}
