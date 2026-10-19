from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import AgentSession


@admin.register(AgentSession)
class AgentSessionAdmin(ReadOnlyAdmin):
    list_display = ("job", "provider", "model", "total_steps", "total_input_tokens",
                    "total_output_tokens", "estimated_cost_usd", "created_at")
    list_filter = ("provider",)
