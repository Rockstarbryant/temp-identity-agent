"""
Site playbooks: record what worked, replay it next time.

RECORDING watches a normal AI-driven run. Only the form-filling phase is kept: from the page
that was opened up to the click that submitted the sign-up (everything after the first email
tool is verification, which differs every time and stays with the AI).

REPLAYING runs those steps in code, with no AI calls. Every typed value comes from a *source*
resolved against the current job's own identity / saved details, so a playbook never contains
anyone's data. Anything unexpected (an element that can't be found, a detail that isn't saved)
stops the replay and hands the page to the AI to carry on.
"""
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from django.utils import timezone

from apps.ai_agent.models import SitePlaybook
from apps.ai_agent.step_detail import is_secret_field

KIND = "registration"
MAX_STEPS = 40
MIN_PERSONAL_LEN = 3  # shorter profile values ("M", "KE") are too generic to count as personal

_SUBMIT_WORDS = re.compile(
    r"\b(sign\s*up|signup|register|create\s+(an\s+)?account|join|submit|continue|next|get\s+started)\b", re.IGNORECASE)
_NOISE = re.compile(r"[^a-z0-9]+")


def norm(text: str) -> str:
    return _NOISE.sub(" ", (text or "").lower()).strip()


def same_site(url: str, domain: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    domain = (domain or "").lower().removeprefix("www.")
    return bool(host) and (host == domain or host.endswith("." + domain) or host.removeprefix("www.") == domain)


# --- Values -------------------------------------------------------------------

def value_sources(identity, profile: dict[str, str]) -> dict[str, str]:
    """source name -> the real value, for this job. Never persisted."""
    values: dict[str, str] = {}
    if identity is not None:
        values["email"] = identity.email or ""
        values["username"] = identity.username or ""
        values["password"] = identity.get_password() if identity.encrypted_password else ""
        full = (identity.name or "").strip()
        parts = full.split()
        values["full_name"] = full
        if parts:
            values["first_name"] = parts[0]
            values["last_name"] = " ".join(parts[1:])
    for key, value in (profile or {}).items():
        if value:
            values[f"profile:{key}"] = str(value)
    return {k: v for k, v in values.items() if v}


def source_for(text: str, values: dict[str, str]) -> str | None:
    """Which source produced exactly this text, if any."""
    for name, value in values.items():
        if text == value:
            return name
    return None


def looks_personal(text: str, values: dict[str, str]) -> bool:
    """True if `text` is, or contains, something that came from the user's own data."""
    t = (text or "").lower()
    for name, value in values.items():
        v = value.lower()
        if name == "password" or len(v) < MIN_PERSONAL_LEN:
            continue
        if v in t or (len(t) >= MIN_PERSONAL_LEN and t in v):
            return True
    return False


# --- Finding elements again ---------------------------------------------------

def target_of(el: dict[str, Any]) -> dict[str, str]:
    return {k: (el.get(k) or "")[:120] for k in ("tag", "type", "label", "name", "placeholder", "group")}


def target_key(t: dict[str, str]) -> str:
    return "|".join(norm(t.get(k, "")) for k in ("tag", "type", "label", "name", "placeholder", "group"))


def find_element(elements: list[dict[str, Any]], target: dict[str, str]) -> dict[str, Any] | None:
    """The one visible element that matches `target`; None if there is no match or it's ambiguous."""
    best_score, best = 0, []
    for el in elements:
        if not el.get("visible", True) or el.get("tag") != target.get("tag"):
            continue
        score = 0
        label, t_label = norm(el.get("label", "")), norm(target.get("label", ""))
        if t_label and label == t_label:
            score += 3
        name, t_name = norm(el.get("name", "")), norm(target.get("name", ""))
        if t_name and name == t_name:
            score += 2
        if (el.get("type") or "") == (target.get("type") or ""):
            score += 1
        if norm(el.get("placeholder", "")) == norm(target.get("placeholder", "")) and target.get("placeholder"):
            score += 1
        if norm(el.get("group", "")) == norm(target.get("group", "")) and target.get("group"):
            score += 1
        if score < 3 or not (t_label and label == t_label or t_name and name == t_name):
            continue
        if score > best_score:
            best_score, best = score, [el]
        elif score == best_score:
            best.append(el)
    return best[0] if len(best) == 1 else None


# --- Recording ----------------------------------------------------------------

@dataclass
class PlaybookRecorder:
    """Watches one run. `observe` is called after every tool call with its outcome."""

    domain: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    broken: bool = False      # something unreplayable happened (personal literal, odd navigation)
    reached_email: bool = False

    def observe(self, ctx, tool_name: str, args: dict[str, Any], element: dict[str, Any] | None, outcome: dict) -> None:
        if self.broken or self.reached_email:
            return
        if tool_name.startswith("email.") or tool_name.startswith("registration.mark_"):
            self.reached_email = tool_name.startswith("email.")
            return
        if not outcome.get("success"):
            return
        handler = {
            "browser.open": self._open, "browser.type": self._type, "browser.select": self._select,
            "browser.click": self._click, "browser.go_back": self._back,
        }.get(tool_name)
        if handler:
            handler(ctx, args, element, outcome)

    # -- helpers
    def _values(self, ctx) -> dict[str, str]:
        from apps.ai_agent.tools import _profile_values

        return value_sources(ctx.identity, _profile_values(ctx.job.user))

    def _drop(self, key: str, ops: tuple[str, ...]) -> None:
        self.steps = [s for s in self.steps if not (s["op"] in ops and target_key(s.get("target", {})) == key)]

    # -- tool handlers
    def _open(self, ctx, args, element, outcome):
        url = str(args.get("url", ""))
        if not same_site(url, self.domain):
            self.broken = True
            return
        self.steps = [{"op": "open", "url": url}]  # the latest page the agent started from wins

    def _type(self, ctx, args, element, outcome):
        if element is None:
            self.broken = True
            return
        text = str(args.get("text", ""))
        source = source_for(text, self._values(ctx))
        if source is None:
            self.broken = True  # a literal we can't vouch for: stop here, the AI continues next time
            return
        target = target_of(element)
        self._drop(target_key(target), ("fill",))
        self.steps.append({"op": "fill", "target": target, "source": source})

    def _select(self, ctx, args, element, outcome):
        if element is None:
            self.broken = True
            return
        value = str(args.get("value", ""))
        values = self._values(ctx)
        source = source_for(value, values)
        if source is None and looks_personal(value, values):
            self.broken = True
            return
        target = target_of(element)
        self._drop(target_key(target), ("select",))
        step: dict[str, Any] = {"op": "select", "target": target}
        step.update({"source": source} if source else {"value": value[:200]})
        self.steps.append(step)

    def _click(self, ctx, args, element, outcome):
        if element is None:
            self.broken = True
            return
        if element.get("tag") == "a" and element.get("href", "").startswith("http") and not same_site(element["href"], self.domain):
            return  # an outbound link is not part of signing up
        target = target_of(element)
        key = target_key(target)
        after = ((outcome.get("result") or {}).get("snapshot") or {}).get("elements", [])
        now = next((e for e in after if e.get("element_id") == element.get("element_id")), None)
        checked = now.get("checked") if now else None
        if checked is not None:  # a checkbox / radio / switch: remember the end state, not the clicks
            self._drop(key, ("check",))
            if checked:
                self.steps.append({"op": "check", "target": target})
            return
        if self.steps and self.steps[-1].get("op") == "click" and target_key(self.steps[-1]["target"]) == key:
            return  # the same click repeated
        self.steps.append({"op": "click", "target": target})

    def _back(self, ctx, args, element, outcome):
        while self.steps and self.steps[-1]["op"] in ("click", "check"):
            self.steps.pop()  # going back undoes the navigation the last click caused
            break

    # -- result
    def build(self) -> list[dict[str, Any]] | None:
        """The steps worth saving, or None if this run can't make a reliable playbook."""
        if self.broken or not self.steps or self.steps[0]["op"] != "open":
            return None
        steps = list(self.steps)
        last_input = max((i for i, s in enumerate(steps) if s["op"] in ("fill", "select", "check")), default=-1)
        if last_input < 0:
            return None
        submit = next(
            (i for i in range(last_input + 1, len(steps))
             if steps[i]["op"] == "click" and _SUBMIT_WORDS.search(steps[i]["target"].get("label", ""))),
            None,
        )
        if submit is None:
            submit = next((i for i in range(last_input + 1, len(steps)) if steps[i]["op"] == "click"), None)
        if submit is None:
            return None
        steps = steps[: submit + 1]
        sources = {s.get("source") for s in steps if s["op"] == "fill"}
        if not {"email", "password"} <= sources or len(steps) > MAX_STEPS:
            return None
        return steps


# --- Storage ------------------------------------------------------------------

def find_playbook(domain: str) -> SitePlaybook | None:
    return SitePlaybook.objects.filter(domain=domain, kind=KIND, disabled=False).first()


def finalize(job, recorder: PlaybookRecorder, used: SitePlaybook | None, replay_ok: bool) -> None:
    """Update (or create) the site's playbook after a run. Never raises."""
    import logging

    try:
        now = timezone.now()
        completed = job.state == job.State.COMPLETED
        if used is not None:
            if completed and replay_ok:
                used.success_count += 1
                used.last_success_at = used.last_used_at = now
                used.save(update_fields=["success_count", "last_success_at", "last_used_at", "updated_at"])
                return
            used.fail_count += 1
            used.last_used_at = now
            if used.fail_count >= 3 and used.fail_count > used.success_count:
                used.disabled = True
            used.save(update_fields=["fail_count", "disabled", "last_used_at", "updated_at"])
        if completed:
            steps = recorder.build()
            if steps:
                SitePlaybook.objects.update_or_create(
                    domain=recorder.domain, kind=KIND,
                    defaults={"steps": steps, "auth_check": job.auth_check or {}, "disabled": False,
                              "fail_count": 0, "last_success_at": now, "last_used_at": now,
                              "success_count": (used.success_count if used else 0) + 1},
                )
    except Exception:  # noqa: BLE001 - bookkeeping must never fail a finished job
        logging.getLogger("apps.ai_agent").exception("Could not update the playbook for %s", recorder.domain)


def describe(step: dict[str, Any]) -> str:
    label = (step.get("target") or {}).get("label") or (step.get("target") or {}).get("name") or "field"
    return {
        "open": f"open {step.get('url', '')}",
        "fill": f"fill “{label}”", "select": f"choose in “{label}”",
        "check": f"tick “{label}”", "click": f"click “{label}”",
    }.get(step["op"], step["op"])
