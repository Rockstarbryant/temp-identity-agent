"""
Human-readable descriptions of agent steps for the job timeline, plus
redaction of secrets before a step is persisted.

The timeline shows what the agent actually did ("Clicked the “Sign up”
button", "Filled “Email” with abc@x.com") instead of just a tool name.
Values typed into password-like fields are never shown or stored.
"""
from typing import Any
from urllib.parse import urlparse

HIDDEN = "[hidden]"
_SECRET_HINTS = ("password", "passcode", "secret", "token", "otp", "cvv", "card number")
_MAX_VALUE = 60
_MAX_DETAIL = 300


def _short(text: str, limit: int = _MAX_VALUE) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def element_label(el: dict[str, Any] | None, element_id: str = "") -> str:
    if not el:
        return element_id
    for key in ("label", "placeholder", "name", "value", "href"):
        val = (el.get(key) or "").strip()
        if val:
            return _short(val, 40)
    return element_id or el.get("tag", "element")


def is_secret_field(el: dict[str, Any] | None) -> bool:
    if not el:
        return False
    if (el.get("type") or "").lower() == "password":
        return True
    hay = " ".join(str(el.get(k) or "") for k in ("name", "label", "placeholder")).lower()
    return any(h in hay for h in _SECRET_HINTS)


def index_elements(outcome: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """element_id -> element dict from a browser tool outcome's snapshot (if any)."""
    snapshot = ((outcome.get("result") or {}).get("snapshot")) or {}
    return {e["element_id"]: e for e in snapshot.get("elements", []) if "element_id" in e}


def describe_step(
    tool_name: str,
    args: dict[str, Any],
    element: dict[str, Any] | None,
    outcome: dict[str, Any],
) -> str:
    ok = bool(outcome.get("success"))
    result = outcome.get("result") or {}
    element_id = str(args.get("element_id", ""))
    label = element_label(element, element_id)

    if tool_name == "browser.open":
        parsed = urlparse(str(args.get("url", "")))
        text = f"Opened {parsed.netloc}{parsed.path.rstrip('/')}" if parsed.netloc else "Opened the page"
    elif tool_name == "browser.inspect":
        snap = result.get("snapshot") or {}
        title = snap.get("title")
        count = len(snap.get("elements", []))
        text = f"Looked at “{_short(title, 50)}” ({count} elements)" if title else f"Looked at the page ({count} elements)"
    elif tool_name == "browser.click":
        kind = "link" if (element or {}).get("tag") == "a" else "button"
        text = f"Clicked the “{label}” {kind}" if element else f"Clicked element {element_id}"
    elif tool_name == "browser.type":
        if is_secret_field(element):
            text = f"Filled “{label}” (hidden)"
        else:
            text = f"Filled “{label}” with {_short(args.get('text', ''))}"
    elif tool_name == "browser.select":
        text = f"Selected “{_short(args.get('value', ''))}” in “{label}”"
    elif tool_name == "browser.scroll":
        text = f"Scrolled {args.get('direction', 'down')}"
    elif tool_name == "browser.go_back":
        text = "Went back a page"
    elif tool_name == "identity.create":
        text = f"Created identity {result['email']}" if result.get("email") else "Created a temporary identity"
    elif tool_name == "identity.get":
        text = "Checked identity details"
    elif tool_name == "identity.update_username":
        text = f"Recorded the username used on the site: {_short(args.get('username', ''))}"
    elif tool_name == "identity.propose_password":
        text = "Generated a new password for the site"
    elif tool_name == "identity.commit_password":
        text = "Saved the new password to the vault"
    elif tool_name == "email.get_mailbox":
        text = f"Checked mailbox {result['address']}" if result.get("address") else "Checked the temporary mailbox"
    elif tool_name == "email.list_messages":
        n = len(result.get("messages", []))
        text = f"Checked for new emails ({n} found)"
    elif tool_name == "email.read_message":
        text = f"Read email “{_short(result.get('subject', ''), 50)}”" if result.get("subject") else "Read an email"
    elif tool_name == "email.wait_for_verification":
        if result.get("received"):
            text = f"Verification email arrived: “{_short(result.get('subject', ''), 50)}”"
        else:
            text = f"No verification email arrived after {args.get('timeout_seconds', 60)}s"
    elif tool_name == "browser.read_text":
        text = "Read the text on the page"
    elif tool_name == "profile.get":
        keys = args.get("keys") or []
        text = f"Looked up your saved details ({', '.join(str(k) for k in keys[:6])})" if keys else "Checked which details you have saved"
    elif tool_name == "user.ask":
        q = _short(args.get("question", ""), 120)
        if not ok:
            text = f"Asked you: “{q}”"
        elif result.get("source") == "saved":
            text = f"Used your saved answer for “{q}”"
        elif result.get("answered"):
            if args.get("sensitive"):
                text = f"You answered: “{q}” (hidden)"
            else:
                text = f"You answered “{q}”: {_short(result.get('answer', ''), 80)}"
        else:
            text = f"Asked you “{q}” — no answer ({_short(result.get('reason', ''), 80)})"
    elif tool_name == "site.report_auth_methods":
        if args.get("email_password"):
            text = "Checked sign-in options: email and password is supported"
        else:
            text = "Checked sign-in options: no email/password sign-in (" + ", ".join(args.get("methods") or ["social only"]) + ")"
    elif tool_name == "form.complete":
        text = f"Submitted the form ({len(args.get('submitted') or [])} answers)"
    elif tool_name == "data.submit_result":
        text = "Saved the extracted information"
    elif tool_name.startswith("registration.mark_"):
        reason = args.get("reason", "")
        text = _short(reason, 200) if reason else ""
    elif tool_name == "registration.get_status":
        text = f"Checked job status ({result.get('state', '')})".replace(" ()", "")
    else:
        text = ""

    if not ok and outcome.get("error"):
        text = f"{text} — failed: {_short(outcome['error'], 120)}" if text else _short(outcome["error"], 160)
    return text[:_MAX_DETAIL]


def redact_for_storage(
    tool_name: str,
    args: dict[str, Any],
    element: dict[str, Any] | None,
    outcome: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Return (tool_input, tool_result) safe to persist/serve: typed secrets and
    the identity password are replaced, and password-type values inside page
    snapshots are blanked. The model still sees the real, unredacted outcome.
    """
    safe_args = dict(args)
    if tool_name == "browser.type" and is_secret_field(element):
        safe_args["text"] = HIDDEN

    safe_outcome = _deepcopy_json(outcome)
    result = safe_outcome.get("result")
    if isinstance(result, dict):
        if tool_name == "identity.get" and "password" in result:
            result["password"] = HIDDEN
        if tool_name == "identity.propose_password" and "new_password" in result:
            result["new_password"] = HIDDEN
        if tool_name == "profile.get" and "values" in result:
            result["values"] = {k: HIDDEN for k in result["values"]}
        if tool_name == "user.ask" and "answer" in result and (args.get("sensitive") or result.get("source") == "saved"):
            result["answer"] = HIDDEN
        snap = result.get("snapshot")
        if isinstance(snap, dict):
            for el in snap.get("elements", []):
                if is_secret_field(el) and el.get("value"):
                    el["value"] = HIDDEN
    return safe_args, safe_outcome


def _deepcopy_json(obj: Any) -> Any:
    import copy

    return copy.deepcopy(obj)
