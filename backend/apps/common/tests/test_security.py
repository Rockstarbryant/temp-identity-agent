import pytest

from apps.common.encryption import CredentialEncryptionError, decrypt_secret, encrypt_secret
from apps.common.exceptions import UnsafeURLError
from apps.common.url_safety import validate_url


class TestEncryption:
    def test_round_trip(self):
        ciphertext = encrypt_secret("my-secret-password")
        assert ciphertext != "my-secret-password"
        assert decrypt_secret(ciphertext) == "my-secret-password"

    def test_tampered_ciphertext_rejected(self):
        ciphertext = encrypt_secret("my-secret-password")
        tampered = ciphertext[:-4] + "abcd"
        with pytest.raises(CredentialEncryptionError):
            decrypt_secret(tampered)

    def test_missing_key_raises(self, settings):
        settings.CREDENTIAL_ENCRYPTION_KEY = None
        with pytest.raises(CredentialEncryptionError):
            encrypt_secret("x")


class TestUrlSafety:
    @pytest.mark.parametrize("url", [
        "http://localhost/",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "ftp://example.com/",
        "not-a-url",
    ])
    def test_unsafe_urls_rejected(self, url):
        with pytest.raises(UnsafeURLError):
            validate_url(url)

    def test_safe_public_url_accepted(self):
        # example.com is a real, stable public domain safe to resolve in tests
        assert validate_url("https://example.com/register") == "https://example.com/register"

    def test_unresolvable_hostname_rejected(self):
        with pytest.raises(UnsafeURLError):
            validate_url("https://this-domain-should-not-resolve-abc123xyz.invalid/")
