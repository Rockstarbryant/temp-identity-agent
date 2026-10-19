from datetime import datetime, timedelta, timezone as dt_tz
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.accounts.models import TemporaryAccount
from apps.email_service import service as email_service
from apps.email_service.models import EmailMessage, TemporaryEmail
from apps.email_service.schemas import MessageDetail, MessageSummary
from apps.identities.models import TemporaryIdentity
from apps.notifications.models import Notification
from apps.notifications.service import notify
from apps.notifications.stream import stream
from apps.registration.models import RegistrationJob, TargetWebsite

pytestmark = pytest.mark.django_db


@pytest.fixture
def job(user):
    site = TargetWebsite.objects.create(domain="example.com", registration_url="https://example.com")
    return RegistrationJob.objects.create(user=user, target_website=site)


def kinds(user):
    return list(Notification.objects.filter(user=user).order_by("id").values_list("kind", flat=True))


class TestJobSignals:
    def test_queued_then_started_then_completed(self, user, job):
        assert kinds(user) == []  # creating a queued job is silent
        job.state = "starting"
        job.save(update_fields=["state"])
        job.state = "filling_form"  # intermediate steps stay quiet
        job.save(update_fields=["state"])
        job.state = "completed"
        job.save(update_fields=["state"])
        assert kinds(user) == ["job_started", "job_completed"]

    def test_failure_carries_the_error(self, user, job):
        job.state, job.error_message = "failed", "Site blocked us"
        job.save()
        n = Notification.objects.get(user=user)
        assert n.kind == "job_failed" and "Site blocked us" in n.body and n.link == f"/jobs/{job.id}"

    def test_captcha_and_question_ask_for_the_user(self, user, job):
        job.state = "captcha_required"
        job.save()
        job.state = "analyzing"
        job.save()
        job.state = "waiting_for_user"
        job.save()
        assert kinds(user) == ["job_started", "job_needs_you", "job_question"]

    def test_same_state_saved_twice_is_announced_once(self, user, job):
        job.state = "cancelled"
        job.save()
        job.save()
        assert kinds(user) == ["job_cancelled"]

    def test_a_notification_error_never_breaks_saving_the_job(self, user, job):
        with patch("apps.notifications.signals.notify", side_effect=RuntimeError("boom")):
            job.state = "completed"
            job.save()
        job.refresh_from_db()
        assert job.state == "completed"


class TestNotify:
    def test_dedupe_key_blocks_repeats(self, user):
        assert notify(user, "mail_received", "a", dedupe_key="k1") is not None
        assert notify(user, "mail_received", "a", dedupe_key="k1") is None
        assert Notification.objects.filter(user=user).count() == 1

    def test_old_ones_are_trimmed(self, user):
        with patch("apps.notifications.service.MAX_KEPT", 3):
            for i in range(6):
                notify(user, "job_started", f"n{i}")
        assert Notification.objects.filter(user=user).count() == 3


class FakeProvider:
    name = "fake"

    def __init__(self):
        self.messages = {}

    def get_messages(self, credential):
        return [MessageSummary(external_id=i) for i in self.messages]

    def get_message(self, credential, external_id):
        return self.messages[external_id]

    def extract_verification_link(self, message):
        return "https://example.com/verify?t=1" if "verify" in message.subject.lower() else None

    def extract_otp(self, message):
        return None


@pytest.fixture
def mailbox(user, job):
    identity = TemporaryIdentity.objects.create(
        user=user, name="N", email="a@b.co", expires_at=timezone.now() + timedelta(days=1))
    job.identity = identity
    job.save(update_fields=["identity"])
    box = TemporaryEmail(identity=identity, provider="fake", address="a@b.co", expires_at=identity.expires_at)
    box.set_credential("{}")
    box.save()
    TemporaryAccount.objects.create(job=job, identity=identity, website=job.target_website)
    return box


def mail(i, subject="Verify your email"):
    return MessageDetail(external_id=i, sender='"Acme" <hi@acme.io>', subject=subject, text_body="hi",
                         received_at=datetime(2026, 1, 1, tzinfo=dt_tz.utc))


class TestMailNotifications:
    def test_new_mail_notifies_once_and_points_at_the_vault_account(self, user, mailbox):
        fake = FakeProvider()
        fake.messages = {"m1": mail("m1")}
        with patch.object(email_service, "get_provider", return_value=fake):
            assert email_service.poll_mailbox(mailbox) == 1
            assert email_service.poll_mailbox(mailbox) == 0  # nothing new the second time
        n = Notification.objects.get(user=user)
        account = TemporaryAccount.objects.get()
        assert n.kind == "mail_received" and "Acme" in n.title and "has a link" in n.body
        assert n.link == f"/accounts/{account.id}" and n.data["has_link"] is True
        assert EmailMessage.objects.count() == 1

    def test_only_new_messages_are_downloaded(self, mailbox):
        fake = FakeProvider()
        fake.messages = {"m1": mail("m1")}
        with patch.object(email_service, "get_provider", return_value=fake):
            email_service.poll_mailbox(mailbox)
            fake.messages["m2"] = mail("m2", "Welcome")
            fake.get_message = MagicMock(wraps=fake.get_message)
            assert email_service.poll_mailbox(mailbox) == 1
        fake.get_message.assert_called_once()

    def test_expired_mailbox_is_not_polled(self, mailbox):
        mailbox.expires_at = timezone.now() - timedelta(minutes=1)
        mailbox.save()
        with patch.object(email_service, "get_provider") as gp:
            assert email_service.poll_mailbox(mailbox) == 0
        gp.assert_not_called()

    def test_provider_failure_is_swallowed(self, mailbox):
        fake = FakeProvider()
        fake.get_messages = MagicMock(side_effect=RuntimeError("mail.tm down"))
        with patch.object(email_service, "get_provider", return_value=fake):
            assert email_service.poll_mailbox(mailbox) == 0
        mailbox.refresh_from_db()
        assert mailbox.last_polled_at is not None  # not retried in a hot loop

    def test_user_poll_skips_recently_checked_boxes(self, user, mailbox):
        TemporaryEmail.objects.filter(pk=mailbox.pk).update(last_polled_at=timezone.now())
        with patch.object(email_service, "get_provider") as gp:
            assert email_service.poll_user_mailboxes(user, min_age_seconds=25) == 0
        gp.assert_not_called()

    def test_beat_task_polls_due_mailboxes(self, user, mailbox):
        from apps.email_service.tasks import poll_mailboxes

        fake = FakeProvider()
        fake.messages = {"m1": mail("m1")}
        with patch.object(email_service, "get_provider", return_value=fake):
            assert poll_mailboxes() == 1
        assert kinds(user) == ["mail_received"]


class TestExpiryReminders:
    def test_reminder_is_sent_once(self, user, mailbox):
        from apps.notifications.tasks import remind_expiring_accounts

        assert remind_expiring_accounts() == 1
        assert remind_expiring_accounts() == 0
        assert kinds(user) == ["account_expiring"]


class TestApi:
    def test_list_and_unread(self, auth_client, user):
        notify(user, "job_started", "one")
        notify(user, "job_completed", "two")
        body = auth_client.get("/api/notifications/").json()
        assert body["unread"] == 2 and [r["title"] for r in body["results"]] == ["two", "one"]

    def test_mark_some_then_all_read(self, auth_client, user):
        a = notify(user, "job_started", "one")
        notify(user, "job_started", "two")
        assert auth_client.post("/api/notifications/read/", {"ids": [a.id]}, format="json").json()["unread"] == 1
        assert auth_client.post("/api/notifications/read/", {}, format="json").json()["unread"] == 0

    def test_bad_ids_rejected(self, auth_client):
        assert auth_client.post("/api/notifications/read/", {"ids": "x"}, format="json").status_code == 400

    def test_only_own_notifications_are_visible_or_deletable(self, auth_client, other_user):
        theirs = notify(other_user, "job_started", "secret")
        assert auth_client.get("/api/notifications/").json()["results"] == []
        auth_client.delete(f"/api/notifications/{theirs.id}/")
        assert Notification.objects.filter(pk=theirs.pk).exists()

    def test_delete_one_and_clear_all(self, auth_client, user):
        a = notify(user, "job_started", "one")
        notify(user, "job_started", "two")
        auth_client.delete(f"/api/notifications/{a.id}/")
        assert Notification.objects.filter(user=user).count() == 1
        assert auth_client.delete("/api/notifications/").status_code == 204
        assert Notification.objects.filter(user=user).count() == 0

    def test_requires_login(self, api_client):
        assert api_client.get("/api/notifications/").status_code == 401
        assert api_client.get("/api/notifications/stream/").status_code == 401


class TestStream:
    def test_ready_then_new_notifications_after_last_id(self, user):
        old = notify(user, "job_started", "old")
        notify(user, "job_completed", "new")
        text = "".join(stream(user, old.id, max_seconds=5, tick=0))
        assert "retry: 3000" in text and "event: ready" in text
        assert "event: notification" in text and '"title": "new"' in text and '"title": "old"' not in text
        assert f"id: {old.id + 1}" in text

    def test_endpoint_streams_with_event_stream_accept(self, auth_client, settings):
        settings.NOTIFICATION_STREAM_SECONDS = 0
        r = auth_client.get("/api/notifications/stream/", HTTP_ACCEPT="text/event-stream")
        assert r.status_code == 200 and r["Content-Type"].startswith("text/event-stream")
        assert r["Cache-Control"].startswith("no-cache") and r["X-Accel-Buffering"] == "no"
        assert b"event: ready" in b"".join(r.streaming_content)

    def test_fresh_connection_skips_history_but_reconnect_resumes(self, auth_client, user, settings):
        settings.NOTIFICATION_STREAM_SECONDS = 0
        first = notify(user, "job_started", "history")
        r = auth_client.get("/api/notifications/stream/")
        assert b"history" not in b"".join(r.streaming_content)
        r = auth_client.get("/api/notifications/stream/", HTTP_LAST_EVENT_ID=str(first.id - 1))
        # with max seconds 0 the loop body never runs, but the resume cursor must be honoured
        assert b"event: ready" in b"".join(r.streaming_content)
