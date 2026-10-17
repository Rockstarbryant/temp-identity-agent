from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from apps.registration.models import AgentQuestion, RegistrationJob, RegistrationStep


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
            "provider", "model", "account_id", "kind", "source", "account_mode",
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


class PendingQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentQuestion
        fields = ["id", "key", "question", "options", "sensitive", "created_at"]
        read_only_fields = fields


class RegistrationJobDetailSerializer(RegistrationJobSerializer):
    steps = RegistrationStepSerializer(many=True, read_only=True)
    pending_question = serializers.SerializerMethodField()
    target_url = serializers.CharField(read_only=True)

    class Meta(RegistrationJobSerializer.Meta):
        fields = RegistrationJobSerializer.Meta.fields + [
            "steps", "pending_question", "result", "auth_check", "target_url", "goal",
        ]
        read_only_fields = fields

    def get_pending_question(self, obj):
        q = obj.questions.filter(status=AgentQuestion.Status.PENDING).order_by("created_at").first()
        return PendingQuestionSerializer(q).data if q else None


class LiveInputSerializer(serializers.Serializer):
    """One user action in the live browser view. Validated strictly: it is replayed in a real browser."""

    type = serializers.ChoiceField(choices=["click", "type", "key", "scroll"])
    x = serializers.IntegerField(required=False, min_value=0, max_value=10000)
    y = serializers.IntegerField(required=False, min_value=0, max_value=10000)
    text = serializers.CharField(required=False, allow_blank=True, max_length=300, trim_whitespace=False)
    submit = serializers.BooleanField(required=False, default=False)
    key = serializers.ChoiceField(
        required=False, choices=sorted(["Enter", "Tab", "Backspace", "Delete", "Escape", "Space",
                                        "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"])
    )
    dy = serializers.IntegerField(required=False, min_value=-1500, max_value=1500)

    def validate(self, attrs):
        kind = attrs["type"]
        required = {"click": ("x", "y"), "type": ("text",), "key": ("key",), "scroll": ("dy",)}[kind]
        missing = [f for f in required if f not in attrs]
        if missing:
            raise serializers.ValidationError({f: "This field is required." for f in missing})
        return attrs
