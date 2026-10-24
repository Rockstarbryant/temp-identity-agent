"""The details Settings offers by default. Anything else is a free-form saved answer."""

STANDARD_FIELDS = [
    {"key": "full_name", "label": "Full name", "type": "text"},
    {"key": "first_name", "label": "First name", "type": "text"},
    {"key": "last_name", "label": "Last name", "type": "text"},
    {"key": "phone", "label": "Phone number", "type": "tel"},
    {"key": "date_of_birth", "label": "Date of birth", "type": "date"},
    {"key": "gender", "label": "Gender", "type": "text"},
    {"key": "nationality", "label": "Nationality", "type": "text"},
    {"key": "country", "label": "Country", "type": "text"},
    {"key": "city", "label": "City / town", "type": "text"},
    {"key": "address", "label": "Address", "type": "text"},
    {"key": "postal_code", "label": "Postal code", "type": "text"},
    {"key": "national_id", "label": "National ID number", "type": "text"},
    {"key": "organization", "label": "Organization", "type": "text"},
    {"key": "job_title", "label": "Job title", "type": "text"},
]

STANDARD_KEYS = {f["key"] for f in STANDARD_FIELDS}
LABELS = {f["key"]: f["label"] for f in STANDARD_FIELDS}

# Never stored as saved answers, whatever the agent or the user tries to save.
BLOCKED_KEYS_HINTS = ("password", "passcode", "pin", "cvv", "card_number", "secret", "token")


def normalize_key(raw: str) -> str:
    """snake_case slug, at most 60 chars."""
    import re

    key = re.sub(r"[^a-z0-9]+", "_", (raw or "").lower()).strip("_")
    return key[:60]


# Single-use codes (an SMS or authenticator code). The agent may ask for one, but it is never
# looked up from, or saved into, the user's saved details: an old code is useless and a stale
# one must never be typed in.
ONE_TIME_KEY_HINTS = ("sms", "otp", "verification", "one_time", "2fa", "mfa", "auth_code", "login_code", "confirmation_code")


def is_blocked_key(key: str) -> bool:
    return any(h in key for h in BLOCKED_KEYS_HINTS)


def is_one_time_key(key: str) -> bool:
    return any(h in key for h in ONE_TIME_KEY_HINTS)


def is_unsavable_key(key: str) -> bool:
    return is_blocked_key(key) or is_one_time_key(key)
