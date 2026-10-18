"""
"Connect a Google/Microsoft account" job: no AI involved.

Opens the provider's sign-in page in the job's own browser, types the saved email
(and password, if one was saved) and, if anything more is needed, hands the browser
to the user through the live view. When the user is signed in, the browser session
(cookies) is saved, encrypted, on their ConnectedAccount for later form jobs.
"""
from django.utils import timezone

from apps.ai_agent.human_hold import hold_for_human
from apps.browser import live_view
from apps.browser.playwright_client import ManagedBrowserSession
from apps.profiles import signin
from apps.registration.models import RegistrationJob


def _set(job: RegistrationJob, state: str, message: str = "", code: str = "") -> None:
    job.state = state
    job.error_code = code
    job.error_message = message
    if state in RegistrationJob.TERMINAL_STATES:
        job.completed_at = timezone.now()
    job.save(update_fields=["state", "error_code", "error_message", "completed_at", "updated_at"])


def run_account_setup(job: RegistrationJob) -> RegistrationJob:
    provider = job.goal
    account = signin.get_account(job.user, provider)
    if account is None or provider not in signin.LOGIN_URLS:
        _set(job, RegistrationJob.State.FAILED, "Add the account in Settings first.", "REGISTRATION_FAILED")
        return job
    name = "Google" if provider == "google" else "Microsoft"

    _set(job, RegistrationJob.State.OPENING_SITE)
    frames = live_view.FramePublisher(job.id)
    with ManagedBrowserSession(job) as session:
        session.goto(signin.LOGIN_URLS[provider])
        result = signin.perform_login(session.page, account)
        if not result.ok:
            _set(job, RegistrationJob.State.HUMAN_ACTION_REQUIRED,
                 result.reason or f"Sign in to {name} in the browser below, then press continue.", "HUMAN_ACTION_REQUIRED")
            if not hold_for_human(job, session, frames):
                job.refresh_from_db(fields=["state"])
                if job.state not in RegistrationJob.TERMINAL_STATES:
                    _set(job, RegistrationJob.State.FAILED, "Timed out waiting for you to sign in. Try again.", "REGISTRATION_FAILED")
                return job
            if signin.is_login_url(provider, session.page.url):
                _set(job, RegistrationJob.State.FAILED,
                     f"It looks like you're not signed in to {name} yet. Try again and finish the sign-in.", "REGISTRATION_FAILED")
                return job

        if not signin.save_session(account, session):
            _set(job, RegistrationJob.State.FAILED, "Signed in, but the browser session could not be saved.", "REGISTRATION_FAILED")
            return job
    job.result = {"note": f"{name} account {account.email} is connected. Forms that need a sign-in will use it."}
    job.save(update_fields=["result", "updated_at"])
    _set(job, RegistrationJob.State.COMPLETED)
    return job
