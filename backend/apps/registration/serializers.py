from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from apps.registration.models import RegistrationJob, RegistrationStep, TargetWebsite


class RegistrationJobCreateSerializer(serializers.Serializer):
    """POST /api/registration-jobs/ body — just the target URL."""

    url = serializers.URLField()

    def validate_url(self, value):
        from apps.common.url_safety import validate_url
        from apps.common.exceptions import UnsafeURLError

        try:
            validate_url(value)
        except UnsafeURLError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value


class RegistrationStepSerializer(serializers.ModelSerializer):
    """
    Timeline entry. Only the outcome and a secret-free description are
    exposed — not the raw tool input/result (which can contain page
    snapshots and typed values).
    """

    success = serializers.SerializerMethodField()
    error = serializers.SerializerMethodField()

    class Meta:
        model = RegistrationStep
        fields = ["step_index", "action", "tool_name", "detail", "success", "error", "created_at"]
        read_only_fields = fields

    def get_success(self, obj) -> bool:
        return bool((obj.tool_result or {}).get("success"))

    def get_error(self, obj) -> str:
        return str((obj.tool_result or {}).get("error", ""))[:300]


class RegistrationJobSerializer(serializers.ModelSerializer):
    domain = serializers.CharField(source="target_website.domain", read_only=True)
    identity_id = serializers.UUIDField(source="identity.id", read_only=True, allow_null=True)
    provider = serializers.SerializerMethodField()
    model = serializers.SerializerMethodField()
    account_id = serializers.SerializerMethodField()

    class Meta:
        model = RegistrationJob
        fields = [
            "id", "domain", "state", "identity_id", "error_code", "error_message",
            "provider", "model", "account_id",
            "created_at", "started_at", "completed_at",
        ]
        read_only_fields = fields

    def _agent_session(self, obj):
        try:
            return obj.agent_session
        except ObjectDoesNotExist:
            return None

    def get_provider(self, obj) -> str:
        session = self._agent_session(obj)
        return session.provider if session else ""

    def get_model(self, obj) -> str:
        session = self._agent_session(obj)
        return session.model if session else ""

    def get_account_id(self, obj):
        try:
            return str(obj.account.id)
        except ObjectDoesNotExist:
            return None


class RegistrationJobDetailSerializer(RegistrationJobSerializer):
    steps = RegistrationStepSerializer(many=True, read_only=True)

    class Meta(RegistrationJobSerializer.Meta):
        fields = RegistrationJobSerializer.Meta.fields + ["steps"]
        read_only_fields = fields
