import string

import pytest

from apps.identities.name_generator import generate_display_name, generate_username
from apps.identities.password_generator import PasswordPolicyError, generate_password
from apps.identities.service import IdentityPermissionError, create_temporary_identity, get_identity_for_user

pytestmark = pytest.mark.django_db


class TestPasswordGenerator:
    def test_respects_length_and_policy(self):
        pw = generate_password(length=20, min_upper=2, min_lower=2, min_digits=2, min_symbols=2)
        assert len(pw) == 20
        assert sum(c in string.ascii_uppercase for c in pw) >= 2
        assert sum(c in string.ascii_lowercase for c in pw) >= 2
        assert sum(c in string.digits for c in pw) >= 2

    def test_impossible_policy_raises(self):
        with pytest.raises(PasswordPolicyError):
            generate_password(length=3, min_upper=2, min_lower=2, min_digits=2, min_symbols=2)

    def test_no_collisions_across_many_generations(self):
        passwords = {generate_password(20, 2, 2, 2, 2) for _ in range(200)}
        assert len(passwords) == 200


class TestNameGenerator:
    def test_username_format(self):
        username = generate_username()
        assert "." in username
        assert username == username.lower()


class TestIdentityService:
    def test_create_persists_and_encrypts(self, user):
        identity = create_temporary_identity(user)
        assert identity.user_id == user.id
        assert identity.encrypted_password != ""
        plaintext = identity.get_password()
        assert len(plaintext) == 20  # default IDENTITY_PASSWORD_LENGTH

    def test_ownership_enforced(self, user, other_user):
        identity = create_temporary_identity(user)
        assert get_identity_for_user(user, identity.id).id == identity.id
        with pytest.raises(IdentityPermissionError):
            get_identity_for_user(other_user, identity.id)


class TestIdentityAPI:
    def test_list_scoped_to_owner(self, auth_client, other_auth_client, user):
        create_temporary_identity(user)
        assert len(auth_client.get("/api/identities/").json()["results"]) == 1
        assert len(other_auth_client.get("/api/identities/").json()["results"]) == 0

    def test_detail_never_exposes_password(self, auth_client, user):
        identity = create_temporary_identity(user)
        r = auth_client.get(f"/api/identities/{identity.id}/")
        assert r.status_code == 200
        assert "password" not in r.json()
        assert "encrypted_password" not in r.json()

    def test_cross_user_detail_returns_404_not_403(self, auth_client, other_auth_client, user):
        identity = create_temporary_identity(user)
        r = other_auth_client.get(f"/api/identities/{identity.id}/")
        assert r.status_code == 404  # not 403 — must not leak existence
