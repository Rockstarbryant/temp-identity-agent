"""
Cryptographically secure password generation.

Uses Python's `secrets` module exclusively — never `random.random()` or
`random.choice()`, which are not suitable for security-sensitive values.
The policy (length, minimum character-class counts) is configurable via
Django settings (sourced from environment variables), never hard-coded.
"""
import secrets
import string

UPPER = string.ascii_uppercase
LOWER = string.ascii_lowercase
DIGITS = string.digits
# Avoid characters that commonly trip up naive form validators or are
# visually ambiguous, while staying broad enough for strong entropy.
SYMBOLS = "!@#$%^&*()-_=+"


class PasswordPolicyError(ValueError):
    pass


def generate_password(
    length: int,
    min_upper: int,
    min_lower: int,
    min_digits: int,
    min_symbols: int,
) -> str:
    """
    Generate a random password satisfying the given minimum character-class
    counts, using a cryptographically secure RNG throughout (including the
    final shuffle — `secrets.SystemRandom`, not `random.shuffle`).
    """
    minimum_required = min_upper + min_lower + min_digits + min_symbols
    if length < minimum_required:
        raise PasswordPolicyError(
            f"length ({length}) is smaller than the sum of minimum "
            f"character-class requirements ({minimum_required})."
        )

    chars = (
        [secrets.choice(UPPER) for _ in range(min_upper)]
        + [secrets.choice(LOWER) for _ in range(min_lower)]
        + [secrets.choice(DIGITS) for _ in range(min_digits)]
        + [secrets.choice(SYMBOLS) for _ in range(min_symbols)]
    )

    remaining = length - len(chars)
    full_pool = UPPER + LOWER + DIGITS + SYMBOLS
    chars += [secrets.choice(full_pool) for _ in range(remaining)]

    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def generate_password_from_settings() -> str:
    """Generate a password using the policy configured in Django settings."""
    from django.conf import settings

    return generate_password(
        length=settings.IDENTITY_PASSWORD_LENGTH,
        min_upper=settings.IDENTITY_PASSWORD_MIN_UPPER,
        min_lower=settings.IDENTITY_PASSWORD_MIN_LOWER,
        min_digits=settings.IDENTITY_PASSWORD_MIN_DIGITS,
        min_symbols=settings.IDENTITY_PASSWORD_MIN_SYMBOLS,
    )
