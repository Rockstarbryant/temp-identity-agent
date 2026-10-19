from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import AgentSession, SitePlaybook


@admin.register(AgentSession)
class AgentSessionAdmin(ReadOnlyAdmin):
    list_display = ("job", "provider", "model", "total_steps", "total_input_tokens",
                    "total_output_tokens", "estimated_cost_usd", "created_at")
    list_filter = ("provider",)


@admin.register(SitePlaybook)
class SitePlaybookAdmin(admin.ModelAdmin):
    """Saved sign-up steps per site. The only editable bit is `disabled`; steps hold no personal data."""

    list_display = ("domain", "kind", "success_count", "fail_count", "disabled", "last_success_at")
    list_filter = ("disabled", "kind")
    search_fields = ("domain",)
    actions = ["disable_selected", "enable_selected"]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields if f.name != "disabled"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Stop using the selected playbooks")
    def disable_selected(self, request, queryset):
        queryset.update(disabled=True)

    @admin.action(description="Use the selected playbooks again (resets failures)")
    def enable_selected(self, request, queryset):
        queryset.update(disabled=False, fail_count=0)
