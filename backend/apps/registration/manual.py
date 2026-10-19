"""
Manual sign-up kit.

When a CAPTCHA (or another human-only step) stops the agent, the job used to
just fail. Instead the agent keeps what it learned: the registration form's
fields, each mapped to the identity value that belongs in it. The user copies
the values into the real form, then records the result, which lands in the
vault like any other account.

The kit stored on the job holds field DESCRIPTORS only (label, type, source).
Real values, including the password, are resolved when the user asks for the
kit, and that request is audit-logged.
"""
import logging

from django.utils import timezone

from apps.ai_agent import playbook as pb

logger = logging.getLogger(__name__)

SKIP_TYPES = {"hidden", "submit", "button", "image", "reset", "search", "file"}
MAX_FIELDS = 40

_RULES = (  # (source, words that must appear in label/name/placeholder)
    ("password", ("password", "passwd", "pwd")),
    ("email", ("email", "e mail")),
    ("username", ("username", "user name", "login", "handle", "nickname")),
    ("first_name", ("first name", "firstname", "given name", "fname")),
    ("last_name", ("last name", "lastname", "surname", "family name", "lname")),
    ("full_name", ("full name", "your name", "name")),
)
_PROFILE_RULES = (
    ("profile:phone", ("phone", "mobile", "tel")),
    ("profile:country", ("country",)),
    ("profile:city", ("city", "town")),
    ("profile:postal_code", ("zip", "postal", "postcode")),
    ("profile:address", ("address", "street")),
    ("profile:date_of_birth", ("birth", "dob", "birthday")),
    ("profile:company", ("company", "organization", "organisation")),
)


def guess_source(el: dict) -> str:
    kind = (el.get("type") or "").lower()
    if kind == "password":
        return "password"
    if kind == "email":
        return "email"
    text = " ".join(pb.norm(el.get(k, "")) for k in ("label", "name", "placeholder"))
    for source, words in _RULES + _PROFILE_RULES:
        if any(w in text for w in words):
            return source
    return ""


def build_kit(snapshot) -> dict:
    """Field descriptors from an inspect_page snapshot. No values."""
    fields, seen = [], set()
    for e in snapshot.elements:
        el = e.model_dump() if hasattr(e, "model_dump") else dict(e)
        tag, kind = el.get("tag"), (el.get("type") or "").lower()
        if not el.get("visible") or tag not in ("input", "select", "textarea") or kind in SKIP_TYPES:
            continue
        label = (el.get("label") or el.get("placeholder") or el.get("name") or "").strip()[:120]
        if not label:
            continue
        key = (pb.norm(label), kind, el.get("group") or "")
        if key in seen:
            continue
        seen.add(key)
        fields.append({
            "label": label,
            "type": "select" if tag == "select" else kind or "text",
            "required": bool(el.get("required")),
            "source": guess_source(el),
            "options": (el.get("options") or [])[:30],
            "group": (el.get("group") or "")[:80],
        })
        if len(fields) >= MAX_FIELDS:
            break
    return {"fields": fields}


def snapshot_into_job(ctx) -> None:
    """Best effort, while the page is still alive. Never raises: a failure here must not hide the CAPTCHA state."""
    try:
        from apps.browser.page_inspector import inspect_page

        if ctx.session is None:
            return
        page = ctx.session.page
        kit = build_kit(inspect_page(page))
        kit.update(url=str(page.url)[:500], title=str(page.title())[:200], created_at=timezone.now().isoformat())
        if not kit["fields"]:
            return
        result = dict(ctx.job.result or {})
        result["manual_kit"] = kit
        previous = ctx.job.result
        ctx.job.result = result
        try:
            ctx.job.save(update_fields=["result", "updated_at"])
        except Exception:
            ctx.job.result = previous  # never leave an unsavable value on the job
            raise
    except Exception:  # noqa: BLE001
        logger.warning("Could not capture the manual sign-up kit for job %s", getattr(ctx.job, "id", "?"), exc_info=True)


def resolve_kit(job, profile: dict) -> dict:
    """The stored kit with real values filled in for display to the owner."""
    kit = (job.result or {}).get("manual_kit") or {}
    values = pb.value_sources(job.identity, profile)
    fields = []
    for f in kit.get("fields", []):
        value = values.get(f.get("source", ""), "")
        fields.append({**f, "value": value, "secret": f.get("type") == "password" or f.get("source") == "password"})
    return {
        "url": kit.get("url") or job.target_website.registration_url,
        "title": kit.get("title", ""),
        "domain": job.target_website.domain,
        "fields": fields,
        "email": job.identity.email if job.identity else "",
        "username": job.identity.username if job.identity else "",
        "password": values.get("password", ""),
    }
