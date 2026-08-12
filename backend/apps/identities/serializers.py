from rest_framework import serializers

from apps.identities.models import TemporaryIdentity


class TemporaryIdentitySerializer(serializers.ModelSerializer):
    """
    Read-only representation of a TemporaryIdentity.

    Deliberately excludes `encrypted_password` — the identity list/detail
    endpoints show metadata only. The password itself is only ever
    revealed through the account-vault "reveal credentials" endpoint
    (apps.accounts, Phase 10), which requires re-authentication and is
    audit-logged.
    """

    class Meta:
        model = TemporaryIdentity
        fields = ["id", "name", "username", "email", "status", "created_at", "expires_at"]
        read_only_fields = fields
