"""
The user's connected inbox (Gmail or IMAP), as ONE inbox.

Each permanent task reads the user's own inbox through its own mailbox row (so the agent only ever
sees mail that arrived after that task started). That is plumbing: the user sees a single inbox with
everything those mailboxes have collected, one "new email" notification per message, and one mute switch.
Disposable mailboxes for temporary identities stay separate, one per account.
"""
from django.utils import timezone

from apps.email_service.models import EmailMessage, TemporaryEmail

OWN_PROVIDERS = ("imap", "gmail")
MAX_MESSAGES = 100


def is_own_inbox(mailbox: TemporaryEmail) -> bool:
    return mailbox.provider in OWN_PROVIDERS


def own_mailboxes(user):
    return TemporaryEmail.objects.filter(identity__user=user, provider__in=OWN_PROVIDERS)


def is_muted(mailbox: TemporaryEmail) -> bool:
    """True when `mailbox` reads the user's own inbox and the user muted it."""
    if not is_own_inbox(mailbox):
        return False
    from apps.profiles.models import EmailConnection

    return EmailConnection.objects.filter(user=mailbox.identity.user, muted=True).exists()


def background_mailbox_ids(now=None) -> set:
    """
    Own-inbox mailboxes the background poller should check: ONE per user (the oldest live one, whose
    baseline covers all later mail), and none for muted users. Everything else is polled as before.
    """
    from apps.profiles.models import EmailConnection

    now = now or timezone.now()
    muted_users = set(EmailConnection.objects.filter(muted=True).values_list("user_id", flat=True))
    chosen: dict = {}
    rows = (TemporaryEmail.objects.filter(provider__in=OWN_PROVIDERS, status=TemporaryEmail.Status.ACTIVE,
                                          expires_at__gt=now)
            .exclude(encrypted_credential="").order_by("created_at").values_list("id", "identity__user_id"))
    for box_id, user_id in rows:
        if user_id not in muted_users and user_id not in chosen:
            chosen[user_id] = box_id
    return set(chosen.values())


def skipped_own_mailbox_ids(now=None) -> set:
    """Own-inbox mailboxes that must NOT be polled in the background (duplicates and muted ones)."""
    all_own = set(TemporaryEmail.objects.filter(provider__in=OWN_PROVIDERS).values_list("id", flat=True))
    return all_own - background_mailbox_ids(now)


def primary_mailbox(user) -> TemporaryEmail | None:
    """The mailbox used to check the inbox on demand: the oldest live one."""
    for box in own_mailboxes(user).filter(status=TemporaryEmail.Status.ACTIVE, expires_at__gt=timezone.now()) \
            .exclude(encrypted_credential="").order_by("created_at"):
        return box
    return None


def _site_labels(user) -> dict[str, str]:
    from apps.accounts.models import TemporaryAccount

    out: dict[str, str] = {}
    for a in (TemporaryAccount.objects.filter(job__user=user, identity__mailbox__provider__in=OWN_PROVIDERS)
              .exclude(status=TemporaryAccount.Status.DELETED).select_related("website")):
        out[a.website.domain] = str(a.id)
    return out


def guess_site(message: EmailMessage, domains: dict[str, str]) -> dict | None:
    """Which saved account an email is probably about, from its sender and subject."""
    hay = f"{message.sender} {message.subject}".lower()
    for domain, account_id in domains.items():
        label = domain.lower().removeprefix("www.").split(".")[0]
        if len(label) >= 4 and label in hay:
            return {"domain": domain, "account_id": account_id}
    return None


def inbox_messages(user, limit: int = MAX_MESSAGES) -> list[EmailMessage]:
    """Every message the user's own-inbox mailboxes hold, newest first, each Gmail message once."""
    seen: set[str] = set()
    out: list[EmailMessage] = []
    qs = EmailMessage.objects.filter(mailbox__in=own_mailboxes(user)).order_by("-received_at", "-created_at")
    for m in qs[: limit * 4]:
        if m.external_id in seen:
            continue
        seen.add(m.external_id)
        out.append(m)
        if len(out) >= limit:
            break
    return out


def mark_read(user, message: EmailMessage) -> None:
    if message.read_at is None:
        now = timezone.now()
        EmailMessage.objects.filter(mailbox__in=own_mailboxes(user), external_id=message.external_id,
                                    read_at__isnull=True).update(read_at=now)
        message.read_at = now
