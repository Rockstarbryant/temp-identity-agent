"""
EmailProvider abstraction.

Every concrete provider (mail.tm today; a paid provider later) implements
this interface. Nothing else in the codebase should import a specific
provider directly — go through apps.email_service.service, which picks
the provider class based on settings.EMAIL_PROVIDER.
"""
from abc import ABC, abstractmethod

from apps.email_service.schemas import (
    MessageDetail,
    MessageSummary,
    ProvisionedMailbox,
    VerificationExtractionResult,
)


class EmailProviderError(Exception):
    pass


class EmailProvider(ABC):
    name: str = "base"

    @abstractmethod
    def create_mailbox(self, local_part: str | None = None) -> ProvisionedMailbox:
        """Provision a new disposable mailbox. Returns its address + auth credential."""
        raise NotImplementedError

    @abstractmethod
    def get_messages(self, credential: str) -> list[MessageSummary]:
        """List messages currently in the mailbox (summary only)."""
        raise NotImplementedError

    @abstractmethod
    def get_message(self, credential: str, external_id: str) -> MessageDetail:
        """Fetch the full content of one message."""
        raise NotImplementedError

    @abstractmethod
    def wait_for_message(
        self, credential: str, timeout_seconds: int = 60, poll_interval_seconds: float = 3.0
    ) -> MessageDetail | None:
        """
        Poll the mailbox until a new message arrives or `timeout_seconds`
        elapses. Returns the first message found, or None on timeout.
        """
        raise NotImplementedError

    def extract_verification_link(self, message: MessageDetail) -> str | None:
        """Default implementation, shared across providers — see extraction.py."""
        from apps.email_service.extraction import find_verification_link

        return find_verification_link(message.html_body or message.text_body)

    def extract_otp(self, message: MessageDetail) -> str | None:
        """Default implementation, shared across providers — see extraction.py."""
        from apps.email_service.extraction import find_otp_code

        return find_otp_code(message.text_body or message.html_body)
