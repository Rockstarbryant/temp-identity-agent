from rest_framework import serializers

from apps.accounts.models import TemporaryAccount


class TemporaryAccountSerializer(serializers.ModelSerializer):
    domain = serializers.CharField(source="website.domain", read_only=True)
    email = serializers.EmailField(source="identity.email", read_only=True)
    username = serializers.CharField(source="identity.username", read_only=True)
    expires_at = serializers.DateTimeField(source="identity.expires_at", read_only=True)

    class Meta:
        model = TemporaryAccount
        fields = ["id", "domain", "email", "username", "status", "revealed_at", "expires_at", "created_at"]
        read_only_fields = fields


class RevealCredentialsResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField()
    password = serializers.CharField()
    domain = serializers.CharField()
    expires_at = serializers.DateTimeField()
