"""Creating jobs: shared by the web API and the MCP endpoint."""
from urllib.parse import urlparse

from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.profiles.models import EmailConnection, UserPreferences
from apps.registration.models import RegistrationJob, TargetWebsite
from apps.registration.tasks import run_registration_job_task


# Hosts that only serve online forms (any path), and hosts that serve forms under a path prefix.
_FORM_HOSTS = {
    "forms.gle", "forms.cloud.microsoft", "forms.office.com", "forms.microsoft.com",
    "form.jotform.com", "eu.jotform.com", "form.typeform.com", "tally.so", "forms.zohopublic.com",
    "forms.monday.com", "forms.app", "forms.clickup.com", "forms.hubspot.com",
}
_FORM_HOST_SUFFIXES = (".typeform.com", ".jotform.com", ".formstack.com", ".wufoo.com", ".smartsheet.com")
_FORM_PATHS = {
    "docs.google.com": ("/forms",),
    "airtable.com": ("/shr", "/app"),
    "www.jotform.com": ("/form/",),
    "jotform.com": ("/form/",),
    "app.smartsheet.com": ("/b/form/",),
}


def is_form_url(url: str) -> bool:
    """True for pasted online forms (Google Forms, Microsoft Forms, Typeform, Jotform, Tally, ...)."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in _FORM_HOSTS or host.endswith(_FORM_HOST_SUFFIXES):
        return True
    return any(parsed.path.startswith(p) for p in _FORM_PATHS.get(host, ()))


is_google_form_url = is_form_url  # old name


def create_job(user, url: str, *, source: str = "web", goal: str = "", account_mode: str | None = None,
               kind: str | None = None, audit_extra: dict | None = None) -> RegistrationJob:
    """Validate, create and enqueue a job. Raises ValidationError for problems the caller should show."""
    domain = urlparse(url).hostname
    if not domain:
        raise ValidationError({"url": "Could not determine a domain from this URL."})

    kind = kind or (RegistrationJob.Kind.FORM if is_form_url(url) else RegistrationJob.Kind.REGISTRATION)
    mode = account_mode or UserPreferences.for_user(user).account_mode
    if kind in (RegistrationJob.Kind.FORM, RegistrationJob.Kind.ACCOUNT_SETUP):
        mode = RegistrationJob.AccountMode.TEMPORARY  # no account is created for a form
    if mode == RegistrationJob.AccountMode.PERMANENT and not EmailConnection.objects.filter(user=user).exists():
        raise ValidationError({
            "detail": "Permanent accounts need your own email so the agent can read verification messages. "
                      "Connect it in Settings, or switch to temporary accounts."
        })

    target_website, _ = TargetWebsite.objects.get_or_create(domain=domain, defaults={"registration_url": url})
    job = RegistrationJob.objects.create(
        user=user, target_website=target_website, target_url=url, kind=kind, source=source,
        account_mode=mode, goal=goal[:1000],
    )
    AuditLog.objects.create(
        user=user, action="job.created", resource_type="RegistrationJob", resource_id=str(job.id),
        metadata={"domain": domain, "kind": kind, "source": source, "mode": mode, **(audit_extra or {})},
    )
    run_registration_job_task.delay(str(job.id))
    job.refresh_from_db()  # the task may already have run (eager) or a worker may be racing us
    return job
