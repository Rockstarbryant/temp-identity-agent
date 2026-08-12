"""
Credential encryption helper.

Uses Fernet (AES-128-CBC + HMAC, authenticated encryption) from the
`cryptography` package. The key is read from CREDENTIAL_ENCRYPTION_KEY
(settings/env) and must never be committed to source control.

Generate a key with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class CredentialEncryptionError(Exception):
    pass


def _get_fernet() -> Fernet:
    key = getattr(settings, "CREDENTIAL_ENCRYPTION_KEY", None)
    if not key:
        raise CredentialEncryptionError(
            "CREDENTIAL_ENCRYPTION_KEY is not configured. Set it in your "
            "environment before storing or reading any credentials."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext secret (e.g. a generated password) for storage."""
    fernet = _get_fernet()
    token = fernet.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a stored secret. Raises CredentialEncryptionError on tamper/bad key."""
    fernet = _get_fernet()
    try:
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise CredentialEncryptionError(
            "Could not decrypt credential — wrong key or corrupted data."
        ) from exc
