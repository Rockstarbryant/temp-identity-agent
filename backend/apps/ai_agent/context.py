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
