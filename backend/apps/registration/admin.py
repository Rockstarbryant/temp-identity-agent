from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import AgentQuestion, DomainPolicy, RegistrationJob, RegistrationStep, TargetWebsite


@admin.register(DomainPolicy)
class DomainPolicyAdmin(admin.ModelAdmin):
    """Editable: this is how you block a website or mark it unsupported / human-only."""

    list_display = ("domain", "status", "reason", "updated_at")
    list_filter = ("status",)
    search_fields = ("domain", "reason")


@admin.register(TargetWebsite)
class TargetWebsiteAdmin(admin.ModelAdmin):
    list_display = ("domain", "registration_url", "created_at")
    search_fields = ("domain",)


class StepInline(admin.TabularInline):
    model = RegistrationStep
    extra = 0
    can_delete = False
    fields = ("step_index", "action", "tool_name", "detail")
    readonly_fields = fields
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(RegistrationJob)
class RegistrationJobAdmin(ReadOnlyAdmin):
    list_display = ("target_website", "user", "kind", "state", "source", "error_code", "created_at")
    list_filter = ("state", "kind", "source", "account_mode")
    search_fields = ("target_website__domain", "target_url", "user__username", "error_message")
    date_hierarchy = "created_at"
    inlines = [StepInline]


@admin.register(RegistrationStep)
class RegistrationStepAdmin(ReadOnlyAdmin):
    list_display = ("job", "step_index", "tool_name", "detail", "created_at")
    search_fields = ("tool_name", "detail", "job__target_website__domain")


@admin.register(AgentQuestion)
class AgentQuestionAdmin(ReadOnlyAdmin):
    secret_fields = ("encrypted_answer",)
    list_display = ("question", "job", "status", "sensitive", "created_at")
    list_filter = ("status", "sensitive")
