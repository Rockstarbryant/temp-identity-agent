"""Per-job state the tool handlers operate against."""
from dataclasses import dataclass

from apps.browser.playwright_client import ManagedBrowserSession
from apps.email_service.models import TemporaryEmail
from apps.identities.models import TemporaryIdentity
from apps.registration.models import RegistrationJob


@dataclass
class AgentContext:
    job: RegistrationJob
    session: ManagedBrowserSession | None = None
    identity: TemporaryIdentity | None = None
    mailbox: TemporaryEmail | None = None
    # Connected Google/Microsoft account support (see apps.profiles.signin).
    provider: str = ""            # "google" | "microsoft" | "" for the page being worked on
    signed_in: bool = False       # a verified sign-in happened in this browser -> session can be saved
    awaiting_signin: bool = False # paused so the user can sign in through the live view
    pending_password: str = ""    # a new password proposed for the site; saved to the vault only once the site accepted it
