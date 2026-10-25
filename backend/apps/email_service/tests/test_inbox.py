"""The connected inbox is one inbox, with one mute switch and one notification per email."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import TemporaryAccount
from apps.email_service import inbox, service
from apps.email_service.models import EmailMessage, TemporaryEmail
from apps.identities.service import create_permanent_identity
from apps.notifications.models import Notification
from apps.profiles.models import EmailConnection
from apps.registration.models import RegistrationJob, TargetWebsite

pytestmark = pytest.mark.django_db


@pytest.fixture
def connection(user):
    c = EmailConnection(user=user, kind="gmail", address="me@gmail.com")
    c.set_secret("refresh")
    c.save()
    return c


def _task(user, domain, minutes_ago):
    """A permanent task whose mailbox reads the user's Gmail."""
    site = TargetWebsite.objects.create(domain=domain, registration_url=f"https://{domain}/signup")
    ident = create_permanent_identity(user)
    job = RegistrationJob.objects.create(user=user, target_website=site, identity=ident, state="completed",
                                         account_mode="permanent")
    box = TemporaryEmail(identity=ident, provider="gmail", address="me@gmail.com", expires_at=ident.expires_at)
    box.set_credential('{"connection_id": "x", "baseline_ts": 1}')
    box.save()
    TemporaryEmail.objects.filter(pk=box.pk).update(created_at=timezone.now() - timedelta(minutes=minutes_ago))
    TemporaryAccount.objects.create(job=job, identity=ident, website=site)
    return box


def _msg(box, ext, subject, sender="x@y.com", read=False):
    return EmailMessage.objects.create(mailbox=box, external_id=ext, subject=subject, sender=sender, text_body="hi",
                                       received_at=timezone.now(), read_at=timezone.now() if read else None)


def test_one_inbox_lists_each_message_once_across_task_mailboxes(auth_client, user, connection):
    a, b = _task(user, "alpha.com", 60), _task(user, "beta.org", 30)
    _msg(a, "m1", "Welcome"); _msg(b, "m1", "Welcome")  # same Gmail message seen by both tasks
    _msg(b, "m2", "Your code from betaorg")
    data = auth_client.get("/api/inbox/").json()
    assert [m["subject"] for m in data["messages"]].count("Welcome") == 1 and len(data["messages"]) == 2
    assert data["mailbox"]["address"] == "me@gmail.com" and data["mailbox"]["muted"] is False
    assert any(m["site"] == "beta.org" for m in data["messages"])  # attributed from the sender/subject


def test_reading_marks_every_copy_read(auth_client, user, connection):
    a, b = _task(user, "alpha.com", 60), _task(user, "beta.org", 30)
    ma, _ = _msg(a, "m1", "Welcome"), _msg(b, "m1", "Welcome")
    full = auth_client.get(f"/api/inbox/messages/{ma.id}/").json()
    assert full["text"] and not EmailMessage.objects.filter(external_id="m1", read_at__isnull=True).exists()
    assert auth_client.get("/api/inbox/").json()["unread"] == 0


def test_other_users_cannot_open_messages(other_auth_client, user, connection):
    m = _msg(_task(user, "alpha.com", 5), "m1", "Private")
    assert other_auth_client.get(f"/api/inbox/messages/{m.id}/").status_code == 404
    assert other_auth_client.get("/api/inbox/").status_code == 404  # they have no connected email


def test_mute_switch_and_background_polling(auth_client, user, connection):
    a, b = _task(user, "alpha.com", 60), _task(user, "beta.org", 30)
    assert inbox.background_mailbox_ids() == {a.id}  # one check per inbox, not one per task
    assert auth_client.patch("/api/email-connection/", {"muted": True}, format="json").json()["muted"] is True
    assert inbox.background_mailbox_ids() == set()
    assert inbox.skipped_own_mailbox_ids() == {a.id, b.id}
    assert auth_client.patch("/api/email-connection/", {"muted": False}, format="json").json()["muted"] is False
    assert inbox.background_mailbox_ids() == {a.id}


def test_one_notification_per_email_and_none_when_muted(user, connection):
    a, b = _task(user, "alpha.com", 60), _task(user, "beta.org", 30)
    service._announce_new_mail(a, _msg(a, "m1", "Welcome"))
    service._announce_new_mail(b, _msg(b, "m1", "Welcome"))
    assert Notification.objects.filter(user=user, kind="mail_received").count() == 1
    EmailConnection.objects.filter(user=user).update(muted=True)
    service._announce_new_mail(a, _msg(a, "m2", "Second"))
    assert Notification.objects.filter(user=user, kind="mail_received").count() == 1


def test_temporary_mailboxes_are_untouched_by_mute(user, connection):
    site = TargetWebsite.objects.create(domain="gamma.io", registration_url="https://gamma.io")
    from apps.identities.service import create_temporary_identity

    ident = create_temporary_identity(user)
    box = TemporaryEmail(identity=ident, provider="mailtm", address="t@x.com", expires_at=ident.expires_at)
    box.set_credential("tok"); box.save()
    EmailConnection.objects.filter(user=user).update(muted=True)
    assert inbox.is_muted(box) is False and box.id not in inbox.skipped_own_mailbox_ids()
