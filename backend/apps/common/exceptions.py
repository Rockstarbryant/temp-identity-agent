"""
Domain exception hierarchy.

Every error the agent/registration pipeline can hit maps to one of
these, matching the error codes in docs/architecture.md. Views catch
these and translate them into safe, user-facing DRF error responses
while the full exception (with stack trace) still goes to the
structured logger.
"""


class TempIdentityAgentError(Exception):
    """Base class for all domain-specific errors in this project."""

    code = "INTERNAL_ERROR"
    default_message = "Something went wrong processing this request."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class UnsupportedWebsiteError(TempIdentityAgentError):
    code = "UNSUPPORTED_WEBSITE"
    default_message = "This website is not supported yet."


class RegistrationNotFoundError(TempIdentityAgentError):
    code = "REGISTRATION_NOT_FOUND"
    default_message = "No registration form could be found on this page."


class CaptchaRequiredError(TempIdentityAgentError):
    code = "CAPTCHA_REQUIRED"
    default_message = "This site requires a CAPTCHA to be solved by a human."


class HumanActionRequiredError(TempIdentityAgentError):
    code = "HUMAN_ACTION_REQUIRED"
    default_message = "This step requires manual action before the agent can continue."


class EmailNotReceivedError(TempIdentityAgentError):
    code = "EMAIL_NOT_RECEIVED"
    default_message = "No verification email arrived in time."


class EmailVerificationFailedError(TempIdentityAgentError):
    code = "EMAIL_VERIFICATION_FAILED"
    default_message = "The verification link or code did not work."


class RegistrationFailedError(TempIdentityAgentError):
    code = "REGISTRATION_FAILED"
    default_message = "Registration could not be completed."


class BrowserError(TempIdentityAgentError):
    code = "BROWSER_ERROR"
    default_message = "The browser automation layer encountered an error."


class AIError(TempIdentityAgentError):
    code = "AI_ERROR"
    default_message = "The AI agent encountered an error."


class RateLimitedError(TempIdentityAgentError):
    code = "RATE_LIMITED"
    default_message = "Too many requests. Please slow down."


class DomainBlockedError(TempIdentityAgentError):
    code = "DOMAIN_BLOCKED"
    default_message = "This domain is not allowed."


class JobExpiredError(TempIdentityAgentError):
    code = "JOB_EXPIRED"
    default_message = "This job has expired."


class UnsafeURLError(TempIdentityAgentError):
    code = "UNSAFE_URL"
    default_message = "This URL cannot be accessed for security reasons."
