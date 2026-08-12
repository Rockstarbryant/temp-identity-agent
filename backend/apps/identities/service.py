"""
Service layer for TemporaryIdentity.

Kept separate from views/serializers so both the DRF API (this phase)
and the AI agent's `identity.create` / `identity.get` tools (Phase 7)
call the exact same, single, tested code path — no duplicated logic.
"""
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from apps.identities.models import TemporaryIdentity
from apps.identities.name_generator import generate_display_name, generate_username
from apps.identities.password_generator import generate_password_from_settings


class IdentityNotFoundError(Exception):
    pass


class IdentityPermissionError(Exception):
    pass


def create_temporary_identity(user, retention_days: int | None = None) -> TemporaryIdentity:
    """
    Generate and persist a new TemporaryIdentity for `user`.

    Note: this does not create the mailbox — that's
    apps.email_service.service.create_mailbox_for_identity (Phase 5),
    called separately once the identity exists.
    """
    retention_days = retention_days or settings.TEMP_ACCOUNT_RETENTION_DAYS
    name = generate_display_name()
    username = generate_username()

    identity = TemporaryIdentity(
        user=user,
        name=name,
        username=username,
        email="",  # filled in once the mailbox is provisioned (Phase 5)
        expires_at=timezone.now() + timedelta(days=retention_days),
    )
    identity.set_password(generate_password_from_settings())
    identity.save()
    return identity


def get_identity_for_user(user, identity_id) -> TemporaryIdentity:
    """Fetch an identity, enforcing that it belongs to `user`."""
    try:
        identity = TemporaryIdentity.objects.get(id=identity_id)
    except TemporaryIdentity.DoesNotExist as exc:
        raise IdentityNotFoundError(str(identity_id)) from exc

    if identity.user_id != user.id:
        raise IdentityPermissionError(
            f"User {user.id} does not own identity {identity_id}."
        )
    return identity


def revoke_identity(identity: TemporaryIdentity) -> TemporaryIdentity:
    """Mark an identity revoked (used on manual delete / early cleanup)."""
    identity.status = TemporaryIdentity.Status.REVOKED
    identity.save(update_fields=["status", "updated_at"])
    return identity
