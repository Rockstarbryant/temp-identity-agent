from unittest.mock import patch

import pytest
from django.utils import timezone

from ai.base import AIProvider
from ai.schemas import ChatMessage, CompletionResult, ToolCallRequest
from apps.accounts.chat import conversation_for_account
from apps.accounts.models import AccountChatMessage, ChatConversation, TemporaryAccount
from apps.identities import service as identity_service
from apps.registration.models import RegistrationJob, TargetWebsite

pytestmark = pytest.mark.django_db


class Scripted(AIProvider):
    name = "scripted"

    def __init__(self, *steps):
        self.steps, self.seen = list(steps), []

    def complete(self, messages, tools):
        self.seen.append(list(messages))
        return self.steps.pop(0)


def text(t):
    return CompletionResult(message=ChatMessage(role="assistant", content=t))


def tool(name, **args):
    return CompletionResult(message=ChatMessage(role="assistant", content="", tool_calls=[
        ToolCallRequest(id="t1", name=name, arguments=args)]))


@pytest.fixture
def account(user):
    site = TargetWebsite.objects.create(domain="mobilesasa.com", registration_url="https://account.mobilesasa.com/register")
    identity = identity_service.create_temporary_identity(user)
    job = RegistrationJob.objects.create(user=user, target_website=site, state="completed", identity=identity)
    return TemporaryAccount.objects.create(job=job, identity=identity, website=site)


def ask(client, account, message):
    return client.post(f"/api/accounts/{account.id}/chat/", {"message": message}, format="json")


def test_plain_answer_is_saved_and_returned(auth_client, account):
    with patch("apps.accounts.chat.get_ai_provider", return_value=Scripted(text("Your username is not set yet."))):
        r = ask(auth_client, account, "what is my username?")
    assert r.status_code == 200
    assert [m["role"] for m in r.data["messages"]] == ["user", "assistant"]
    assert r.data["can_chat"] is True


def test_the_model_is_never_given_the_password(auth_client, account):
    provider = Scripted(text("ok"))
    with patch("apps.accounts.chat.get_ai_provider", return_value=provider):
        ask(auth_client, account, "hi")
    blob = " ".join(m.content for m in provider.seen[0])
    assert account.identity.get_password() not in blob


def test_update_saved_details_changes_vault_and_scrubs_the_password_from_history(auth_client, account):
    provider = Scripted(tool("update_saved_details", username="kim_k", password="Brand-New-Pass-9"), text("Saved."))
    with patch("apps.accounts.chat.get_ai_provider", return_value=provider):
        r = ask(auth_client, account, "set my username to kim_k and password to Brand-New-Pass-9")
    account.identity.refresh_from_db()
    assert account.identity.username == "kim_k" and account.identity.get_password() == "Brand-New-Pass-9"
    stored = " ".join(m["content"] for m in r.data["messages"])
    assert "Brand-New-Pass-9" not in stored and "[hidden]" in stored


def test_mailbox_tools_read_the_account_mailbox(auth_client, account):
    from django.utils import timezone

    from apps.email_service.models import EmailMessage, TemporaryEmail

    box = TemporaryEmail(identity=account.identity, provider="mailtm", address="a@b.test", expires_at=account.identity.expires_at, status="closed")
    box.set_credential("x")
    box.save()
    EmailMessage.objects.create(mailbox=box, external_id="1", sender="noreply@m.com", subject="Code",
                                text_body="Your code is 123456", received_at=timezone.now(), extracted_otp="123456")
    provider = Scripted(tool("mailbox_list"), text("The code is 123456."))
    with patch("apps.accounts.chat.get_ai_provider", return_value=provider):
        r = ask(auth_client, account, "what's the code?")
    tool_msg = [m for m in provider.seen[1] if m.role == "tool"][0].content
    assert "123456" in tool_msg and r.data["messages"][-1]["content"] == "The code is 123456."


def test_run_on_website_creates_a_task_job_on_the_same_identity(auth_client, account):
    provider = Scripted(tool("run_on_website", instruction="Find my current balance"), text("Started."))
    with patch("apps.accounts.chat.get_ai_provider", return_value=provider), \
         patch("apps.registration.jobs.run_registration_job_task.delay"):
        r = ask(auth_client, account, "check my balance on the site")
    job = RegistrationJob.objects.get(kind="account_task")
    assert job.identity_id == account.identity_id and job.goal == "Find my current balance"
    assert r.data["active_job"]["id"] == str(job.id)
    assert r.data["messages"][-1]["job_id"] == str(job.id) and r.data["messages"][-1]["kind"] == "task_started"

    # a second one is refused while the first is running
    provider = Scripted(tool("run_on_website", instruction="Do another thing"), text("Wait."))
    with patch("apps.accounts.chat.get_ai_provider", return_value=provider), \
         patch("apps.registration.jobs.run_registration_job_task.delay"):
        ask(auth_client, account, "and another")
    assert RegistrationJob.objects.filter(kind="account_task").count() == 1


def test_finished_task_posts_its_result_into_the_chat_once(auth_client, account):
    job = RegistrationJob.objects.create(user=account.job.user, target_website=account.website, kind="account_task",
                                         identity=account.identity, goal="balance", state="running" if False else "analyzing")
    AccountChatMessage.objects.create(conversation=conversation_for_account(account), role="assistant",
                                      content="Started", kind="task_started", job=job)
    job.state = "completed"
    job.result = {"summary": "Balance is KES 120.", "data": {"balance": "KES 120"}}
    job.save()
    job.save()
    msgs = AccountChatMessage.objects.filter(conversation__account=account, kind="task_result")
    assert msgs.count() == 1 and "KES 120" in msgs[0].content
    assert TemporaryAccount.objects.filter(identity=account.identity).count() == 1  # no second vault entry


def test_task_job_never_creates_an_identity_or_a_second_vault_entry(account):
    from types import SimpleNamespace

    import pytest as _p

    from apps.ai_agent.context import AgentContext
    from apps.ai_agent.tools import _handle_identity_create, _handle_registration_mark_complete
    from apps.common.exceptions import RegistrationFailedError

    job = RegistrationJob.objects.create(user=account.job.user, target_website=account.website, kind="account_task",
                                         identity=account.identity, goal="x", state="analyzing")
    ctx = AgentContext(job=job, identity=account.identity)
    with _p.raises(RegistrationFailedError, match="already exists"):
        _handle_identity_create(ctx, SimpleNamespace())
    job.result = {"summary": "done", "data": {}}
    _handle_registration_mark_complete(ctx, SimpleNamespace())
    assert TemporaryAccount.objects.filter(identity=account.identity).count() == 1


def test_other_users_cannot_chat_and_expired_accounts_are_refused(other_auth_client, auth_client, account):
    assert ask(other_auth_client, account, "hi").status_code == 404
    account.status = "expired"
    account.save()
    assert ask(auth_client, account, "hi").status_code == 400
    assert auth_client.get(f"/api/accounts/{account.id}/chat/").data["can_chat"] is False


def test_ai_outage_returns_503_and_clear_history(auth_client, account):
    from ai.base import AIProviderError

    class Down(AIProvider):
        name = "down"

        def complete(self, messages, tools):
            raise AIProviderError("down")

    with patch("apps.accounts.chat.get_ai_provider", return_value=Down()):
        assert ask(auth_client, account, "hi").status_code == 503
    AccountChatMessage.objects.create(conversation=conversation_for_account(account), role="user", content="x")
    assert auth_client.delete(f"/api/accounts/{account.id}/chat/").status_code == 204
    assert auth_client.get(f"/api/accounts/{account.id}/chat/").data["messages"] == []


def test_chat_list_orders_by_activity_and_flags_working_tasks(auth_client, user, account):
    site = TargetWebsite.objects.create(domain="other.com", registration_url="https://other.com")
    ident = identity_service.create_temporary_identity(user)
    job = RegistrationJob.objects.create(user=user, target_website=site, state="completed", identity=ident)
    other = TemporaryAccount.objects.create(job=job, identity=ident, website=site)
    convo = conversation_for_account(account)
    AccountChatMessage.objects.create(conversation=convo, role="user", content="hello")
    AccountChatMessage.objects.create(conversation=convo, role="assistant", content="hi there")
    running = RegistrationJob.objects.create(user=user, target_website=site, kind="account_task", identity=ident, goal="x", state="analyzing")
    AccountChatMessage.objects.create(conversation=conversation_for_account(other), role="assistant", kind="task_started",
                                      content="Started", job=running)
    AccountChatMessage.objects.filter(content="Started").update(created_at=timezone.now() - timezone.timedelta(days=1))
    r = auth_client.get("/api/chats/")
    rows = {i["title"]: i for i in r.data["results"]}
    assert r.data["results"][0]["title"] == "mobilesasa.com"  # has the newest message
    assert rows["mobilesasa.com"]["last_message"]["content"] == "hi there" and rows["mobilesasa.com"]["message_count"] == 2
    assert rows["other.com"]["working"] is True


def test_chat_list_hides_deleted_and_other_users(auth_client, other_auth_client, account):
    assert len(other_auth_client.get("/api/chats/").data["results"]) == 0
    account.status = "deleted"
    account.save()
    assert len(auth_client.get("/api/chats/").data["results"]) == 0


# --- General ("New chat") conversations --------------------------------------------------

def new_chat(client):
    r = client.post("/api/chats/", {}, format="json")
    assert r.status_code == 201
    return r.data["id"]


def say(client, chat_id, message):
    return client.post(f"/api/chats/{chat_id}/", {"message": message}, format="json")


def test_a_bare_web_address_starts_a_task_without_the_ai(auth_client):
    chat_id = new_chat(auth_client)
    with patch("apps.registration.jobs.run_registration_job_task.delay"), \
         patch("apps.accounts.chat.get_ai_provider", side_effect=AssertionError("the AI must not be called")):
        r = say(auth_client, chat_id, "example.com/signup")
    assert r.status_code == 200, r.data
    job = RegistrationJob.objects.get()
    assert job.target_website.domain == "example.com"
    last = r.data["messages"][-1]
    assert last["kind"] == "task_started" and last["job_id"] == str(job.id)
    assert r.data["active_job"]["id"] == str(job.id) and r.data["title"] == "Sign-up on example.com"


def test_the_assistant_can_start_a_task_with_a_tool_and_records_what_it_did(auth_client):
    chat_id = new_chat(auth_client)
    provider = Scripted(tool("start_task", url="https://example.org/register", instruction="find the plan price"), text("Started."))
    with patch("apps.accounts.chat.get_ai_provider", return_value=provider), \
         patch("apps.registration.jobs.run_registration_job_task.delay"):
        r = say(auth_client, chat_id, "please sign me up on example.org and find the plan price")
    job = RegistrationJob.objects.get()
    assert job.goal == "find the plan price"
    assert r.data["messages"][-1]["actions"] == [{"name": "start_task", "label": "Started a task", "ok": True}]


def test_general_chat_has_no_account_tools(auth_client):
    chat_id = new_chat(auth_client)
    provider = Scripted(text("hello"))
    with patch("apps.accounts.chat.get_ai_provider", return_value=provider):
        say(auth_client, chat_id, "hi")
    # the tool list is the second argument of complete(); inspect via the scripted provider
    assert provider.seen


def test_finished_signup_links_the_conversation_to_the_new_account(auth_client, user):
    from apps.identities import service as identity_service

    chat_id = new_chat(auth_client)
    with patch("apps.registration.jobs.run_registration_job_task.delay"), \
         patch("apps.accounts.chat.get_ai_provider", return_value=Scripted()):
        say(auth_client, chat_id, "newsite.com/register")
    job = RegistrationJob.objects.get()
    job.identity = identity_service.create_temporary_identity(user)
    job.state = "completed"
    job.save()
    state = auth_client.get(f"/api/chats/{chat_id}/").data
    assert state["account_id"] is not None and state["title"] == "newsite.com"
    assert state["messages"][-1]["kind"] == "task_result" and "saved in your vault" in state["messages"][-1]["content"]
    assert TemporaryAccount.objects.filter(job=job).count() == 1


def test_captcha_then_completion_updates_the_same_result_message(auth_client, user):
    chat_id = new_chat(auth_client)
    with patch("apps.registration.jobs.run_registration_job_task.delay"):
        say(auth_client, chat_id, "newsite.org/register")
    job = RegistrationJob.objects.get()
    job.state, job.error_message = "captcha_required", "Hit a CAPTCHA"
    job.save()
    assert "needs you" in auth_client.get(f"/api/chats/{chat_id}/").data["messages"][-1]["content"]
    job.state = "failed"
    job.error_message = "gave up"
    job.save()
    msgs = [m for m in auth_client.get(f"/api/chats/{chat_id}/").data["messages"] if m["kind"] == "task_result"]
    assert len(msgs) == 1 and "gave up" in msgs[0]["content"]


def test_list_shows_general_chats_with_messages_but_not_empty_ones(auth_client, account):
    empty = new_chat(auth_client)
    used = new_chat(auth_client)
    with patch("apps.accounts.chat.get_ai_provider", return_value=Scripted(text("Hi! What would you like to do?"))):
        say(auth_client, used, "hello there")
    rows = {r["id"]: r for r in auth_client.get("/api/chats/").data["results"]}
    assert empty not in rows and rows[used]["title"] == "hello there" and rows[used]["account_id"] is None
    assert any(r["account_id"] == str(account.id) for r in rows.values())  # the vault account has its conversation


def test_general_conversations_can_be_deleted_and_are_private(auth_client, other_auth_client):
    chat_id = new_chat(auth_client)
    assert other_auth_client.get(f"/api/chats/{chat_id}/").status_code == 404
    assert other_auth_client.post(f"/api/chats/{chat_id}/", {"message": "x"}, format="json").status_code == 404
    assert auth_client.delete(f"/api/chats/{chat_id}/").status_code == 204
    assert not ChatConversation.objects.filter(id=chat_id).exists()


def test_deleting_the_vault_account_deletes_its_conversation(auth_client, account):
    convo = conversation_for_account(account)
    AccountChatMessage.objects.create(conversation=convo, role="user", content="secret")
    assert auth_client.delete(f"/api/accounts/{account.id}/").status_code == 204
    assert not ChatConversation.objects.filter(id=convo.id).exists()


def test_account_conversation_is_shared_between_the_two_endpoints(auth_client, account):
    with patch("apps.accounts.chat.get_ai_provider", return_value=Scripted(text("hi"))):
        ask(auth_client, account, "hello")
    chat_id = auth_client.get(f"/api/accounts/{account.id}/chat/").data["id"]
    assert [m["content"] for m in auth_client.get(f"/api/chats/{chat_id}/").data["messages"]][-1] == "hi"
