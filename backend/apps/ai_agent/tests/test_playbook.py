import json
from unittest.mock import patch

import pytest

from ai.base import AIProvider
from ai.schemas import ChatMessage, CompletionResult, ToolCallRequest
from apps.ai_agent import playbook as pb
from apps.ai_agent.models import SitePlaybook
from apps.email_service.models import TemporaryEmail
from apps.registration.models import RegistrationJob, TargetWebsite

pytestmark = pytest.mark.django_db

URL = "https://example.com/register"


def el(eid, tag="input", type="", label="", name="", **kw):
    base = {"element_id": eid, "tag": tag, "type": type, "name": name, "label": label, "placeholder": "", "href": "",
            "value": "", "visible": True, "options": [], "group": "", "checked": None, "required": False}
    base.update(kw)
    return base


def form_elements(with_password=True):
    out = [
        el("e1", type="email", label="Email address", name="email"),
        el("c1", type="checkbox", label="I agree to the Terms", name="tos", checked=False),
        el("b1", tag="button", label="Sign up"),
        el("b2", tag="button", label="Cancel"),
    ]
    if with_password:
        out.insert(1, el("p1", type="password", label="Password", name="pw"))
    return out


class _Loc:
    def __init__(self, page, eid):
        self.page, self.eid = page, eid

    def count(self):
        return 1 if self.eid in self.page.elements else 0

    @property
    def first(self):
        return self

    def fill(self, text):
        self.page.elements[self.eid]["value"] = text
        self.page.log.append(("fill", self.eid, text))

    def click(self):
        e = self.page.elements[self.eid]
        if e["checked"] is not None:
            e["checked"] = not e["checked"]
        self.page.log.append(("click", self.eid, ""))

    def select_option(self, value):
        self.page.log.append(("select", self.eid, value))


class _Page:
    def __init__(self, elements):
        self.elements = {e["element_id"]: dict(e) for e in elements}
        self.url = URL
        self.log = []

    def title(self):
        return "Sign up"

    def evaluate(self, js):
        if "innerText" in js and "querySelectorAll" not in js:
            return "Check your email"
        return [dict(e) for e in self.elements.values()]

    def locator(self, selector):
        return _Loc(self, selector.split('"')[1])


def session_factory(page_holder):
    class _Session:
        def __init__(self, job, headless=True, storage_state=None):
            self.page = page_holder["page"]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def goto(self, url):
            self.page.url = url

    return _Session


class _Provider(AIProvider):
    name = "scripted"

    def __init__(self, steps):
        self.steps = list(steps)
        self.calls = 0

    def complete(self, messages, tools):
        self.calls += 1
        self.last_messages = messages
        return self.steps.pop(0)()


def _all_text(provider):
    return "\n".join(m.content or "" for m in provider.last_messages)


def call(i, name, **args):
    return lambda: CompletionResult(message=ChatMessage(role="assistant", content="", tool_calls=[
        ToolCallRequest(id=f"c{i}", name=name, arguments=args)]))


def fake_mailbox(identity):
    box = TemporaryEmail(identity=identity, provider="mailtm", address=f"{identity.id.hex[:8]}@test.example",
                         expires_at=identity.expires_at)
    box.set_credential("jwt")
    box.save()
    identity.email = box.address
    identity.save(update_fields=["email"])
    return box


def new_job(user):
    site, _ = TargetWebsite.objects.get_or_create(domain="example.com", defaults={"registration_url": URL})
    return RegistrationJob.objects.create(user=user, target_website=site, max_steps=20, timeout_seconds=60)


def run(job, provider, page):
    from apps.ai_agent.agent_loop import AgentRunner

    with patch("apps.ai_agent.agent_loop.ManagedBrowserSession", session_factory({"page": page})), \
         patch("apps.ai_agent.agent_loop.get_ai_provider", return_value=provider), \
         patch("apps.email_service.service.create_mailbox_for_identity", side_effect=fake_mailbox):
        AgentRunner(job).run(URL)
    job.refresh_from_db()


def first_run_script(job):
    """The AI signs up the long way, including a wasted loop (clicks Sign up before the form is ready)."""
    ident = lambda: job.identity  # noqa: E731
    return [
        call(1, "identity.create"),
        call(2, "browser.open", url=URL),
        lambda: call(3, "browser.type", element_id="e1", text=ident().email)(),
        lambda: call(4, "browser.type", element_id="p1", text=ident().get_password())(),
        call(5, "browser.click", element_id="c1"),
        call(6, "browser.click", element_id="c1"),   # toggled off...
        call(7, "browser.click", element_id="c1"),   # ...and on again
        call(8, "browser.click", element_id="b1"),
        call(9, "browser.click", element_id="b1"),   # repeated click
        call(10, "registration.mark_complete"),
    ]


class TestRecordingAndReplay:
    def test_a_completed_run_saves_a_clean_playbook_with_no_personal_data(self, user):
        job = new_job(user)
        page = _Page(form_elements())
        run(job, _Provider(first_run_script(job)), page)
        assert job.state == "completed"

        playbook = SitePlaybook.objects.get(domain="example.com")
        ops = [(s["op"], (s.get("target") or {}).get("label"), s.get("source")) for s in playbook.steps]
        assert ops == [
            ("open", None, None), ("fill", "Email address", "email"), ("fill", "Password", "password"),
            ("check", "I agree to the Terms", None), ("click", "Sign up", None),
        ]
        blob = json.dumps(playbook.steps)
        assert job.identity.email not in blob and job.identity.get_password() not in blob
        assert playbook.success_count == 1

    def test_second_run_replays_without_the_ai_for_the_form(self, user, other_user):
        first = new_job(user)
        run(first, _Provider(first_run_script(first)), _Page(form_elements()))

        second = new_job(other_user)
        provider = _Provider([call(1, "registration.mark_complete")])
        page = _Page(form_elements())
        run(second, provider, page)

        assert second.state == "completed"
        assert provider.calls == 1  # the AI was only needed to finish, not to fill the form
        fills = {eid: text for op, eid, text in page.log if op == "fill"}
        assert fills["e1"] == second.identity.email and fills["p1"] == second.identity.get_password()
        assert fills["e1"] != first.identity.email  # a fresh identity, never the first user's
        assert ("click", "c1", "") in page.log and ("click", "b1", "") in page.log
        details = list(second.steps.values_list("detail", flat=True))
        assert details[0].startswith("Using the steps saved for example.com")
        assert "Do NOT fill the form again" in _all_text(provider)
        SitePlaybook.objects.get(domain="example.com").success_count == 2

    def test_replay_stops_when_the_site_changed_and_the_ai_carries_on(self, user, other_user):
        first = new_job(user)
        run(first, _Provider(first_run_script(first)), _Page(form_elements()))

        second = new_job(other_user)
        provider = _Provider([call(1, "registration.mark_failed", reason="site changed")])
        page = _Page(form_elements(with_password=False))  # the password field is gone
        run(second, provider, page)

        note = _all_text(provider)
        assert "stopped" in note and "Password" in note and "carry on yourself" in note
        playbook = SitePlaybook.objects.get(domain="example.com")
        assert playbook.fail_count == 1 and playbook.success_count == 1

    def test_a_playbook_is_switched_off_after_repeated_failures(self, user):
        pbk = SitePlaybook.objects.create(domain="example.com", steps=[{"op": "open", "url": URL}], success_count=1)
        job = new_job(user)
        job.state = "failed"
        for _ in range(3):
            pb.finalize(job, pb.PlaybookRecorder(domain="example.com"), pbk, replay_ok=False)
            pbk.refresh_from_db()
        assert pbk.fail_count == 3 and pbk.disabled is True
        assert pb.find_playbook("example.com") is None

    def test_failed_runs_never_create_playbooks(self, user):
        job = new_job(user)
        run(job, _Provider([call(1, "registration.mark_failed", reason="nope")]), _Page(form_elements()))
        assert SitePlaybook.objects.count() == 0

    def test_resumed_runs_neither_replay_nor_record(self, user):
        from apps.ai_agent.agent_loop import AgentRunner

        SitePlaybook.objects.create(domain="example.com", steps=[{"op": "open", "url": URL}])
        job = new_job(user)
        job.state = "analyzing"
        job.save()
        provider = _Provider([call(1, "registration.mark_failed", reason="gave up")])
        with patch("apps.ai_agent.agent_loop.ManagedBrowserSession", session_factory({"page": _Page(form_elements())})), \
             patch("apps.ai_agent.agent_loop.get_ai_provider", return_value=provider):
            AgentRunner(job).run(URL, resume=True)
        assert not job.steps.filter(action="playbook.replay").exists()
        assert SitePlaybook.objects.get().fail_count == 0


class TestRecorderRules:
    def make(self, user):
        from apps.ai_agent.context import AgentContext
        from apps.identities import service as identity_service

        job = new_job(user)
        identity = identity_service.create_temporary_identity(user)
        return pb.PlaybookRecorder(domain="example.com"), AgentContext(job=job, identity=identity), identity

    def test_typing_something_that_is_not_an_identity_value_stops_recording(self, user):
        rec, ctx, _ = self.make(user)
        rec.observe(ctx, "browser.open", {"url": URL}, None, {"success": True})
        rec.observe(ctx, "browser.type", {"text": "Some Company Ltd"}, el("x", label="Company"), {"success": True})
        assert rec.broken and rec.build() is None

    def test_failed_calls_and_other_sites_are_ignored(self, user):
        rec, ctx, ident = self.make(user)
        rec.observe(ctx, "browser.open", {"url": URL}, None, {"success": True})
        rec.observe(ctx, "browser.type", {"text": ident.email}, el("e1", label="Email"), {"success": False})
        assert [s["op"] for s in rec.steps] == ["open"]
        rec.observe(ctx, "browser.open", {"url": "https://evil.test/x"}, None, {"success": True})
        assert rec.broken

    def test_recording_stops_at_the_first_email_tool(self, user):
        rec, ctx, ident = self.make(user)
        rec.observe(ctx, "browser.open", {"url": URL}, None, {"success": True})
        rec.observe(ctx, "email.wait_for_verification", {}, None, {"success": True})
        rec.observe(ctx, "browser.open", {"url": "https://example.com/verify?t=1"}, None, {"success": True})
        assert [s["op"] for s in rec.steps] == ["open"] and rec.reached_email

    def test_needs_email_and_password_and_a_submit_click(self, user):
        rec, ctx, ident = self.make(user)
        rec.observe(ctx, "browser.open", {"url": URL}, None, {"success": True})
        rec.observe(ctx, "browser.type", {"text": ident.email}, el("e1", label="Email"), {"success": True})
        rec.observe(ctx, "browser.click", {}, el("b1", tag="button", label="Sign up"), {"success": True})
        assert rec.build() is None  # no password step

    def test_going_back_undoes_the_last_click(self, user):
        rec, ctx, _ = self.make(user)
        rec.observe(ctx, "browser.open", {"url": URL}, None, {"success": True})
        rec.observe(ctx, "browser.click", {}, el("b9", tag="button", label="Next"), {"success": True})
        rec.observe(ctx, "browser.go_back", {}, None, {"success": True})
        assert [s["op"] for s in rec.steps] == ["open"]


class TestMatching:
    def test_element_found_by_label_even_with_a_new_id(self):
        target = pb.target_of(el("old-id", type="email", label="Email address", name="email"))
        found = pb.find_element([el("new-id", type="email", label="Email  Address:", name="email")], target)
        assert found["element_id"] == "new-id"

    def test_ambiguous_or_missing_matches_return_none(self):
        target = pb.target_of(el("x", tag="button", label="Sign up"))
        two = [el("a", tag="button", label="Sign up"), el("b", tag="button", label="Sign up")]
        assert pb.find_element(two, target) is None
        assert pb.find_element([el("c", tag="button", label="Log in")], target) is None
        hidden = [el("d", tag="button", label="Sign up", visible=False)]
        assert pb.find_element(hidden, target) is None

    def test_personal_value_detection(self):
        values = {"profile:phone": "0712345678", "password": "hunter2hunter2", "first_name": "Jo"}
        assert pb.looks_personal("0712345678", values) and pb.looks_personal("call 0712345678 now", values)
        assert not pb.looks_personal("Kenya", values) and not pb.looks_personal("hunter2hunter2", values)
        assert not pb.looks_personal("Jo", values)  # too short to be meaningful

    def test_same_site(self):
        assert pb.same_site("https://www.example.com/a", "example.com")
        assert pb.same_site("https://auth.example.com/a", "example.com")
        assert not pb.same_site("https://example.com.evil.test/a", "example.com")
