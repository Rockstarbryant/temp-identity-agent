"""
Pydantic schemas for the email provider abstraction.

These are the shapes every EmailProvider implementation must return,
regardless of the underlying API's own response format — the mail.tm
provider (or any future provider) is responsible for mapping its raw
API response onto these.
"""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class ProvisionedMailbox(BaseModel):
    """Result of creating a new disposable mailbox."""

    address: EmailStr
    provider: str
    # Opaque credential the provider needs to authenticate later calls
    # (e.g. mail.tm's JWT). Callers must encrypt this before persisting —
    # see apps.email_service.models.TemporaryEmail.set_credential().
    credential: str
    provider_account_id: str = ""


class MessageSummary(BaseModel):
    """One row from a mailbox listing — enough to decide what to fetch in full."""

    external_id: str
    sender: str = ""
    subject: str = ""
    received_at: datetime | None = None
    seen: bool = False


class MessageDetail(BaseModel):
    """Full content of a single message."""

    external_id: str
    sender: str = ""
    subject: str = ""
    text_body: str = ""
    html_body: str = ""
    received_at: datetime | None = None


class VerificationExtractionResult(BaseModel):
    """Output of scanning a message for a verification link and/or OTP."""

    link: str | None = None
    otp: str | None = Field(default=None, max_length=20)
