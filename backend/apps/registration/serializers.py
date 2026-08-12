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
    class Meta:
        model = RegistrationStep
        fields = ["step_index", "action", "tool_name", "tool_result", "created_at"]
        read_only_fields = fields


class RegistrationJobSerializer(serializers.ModelSerializer):
    domain = serializers.CharField(source="target_website.domain", read_only=True)
    identity_id = serializers.UUIDField(source="identity.id", read_only=True, allow_null=True)

    class Meta:
        model = RegistrationJob
        fields = [
            "id", "domain", "state", "identity_id", "error_code", "error_message",
            "created_at", "started_at", "completed_at",
        ]
        read_only_fields = fields


class RegistrationJobDetailSerializer(RegistrationJobSerializer):
    steps = RegistrationStepSerializer(many=True, read_only=True)

    class Meta(RegistrationJobSerializer.Meta):
        fields = RegistrationJobSerializer.Meta.fields + ["steps"]
        read_only_fields = fields
