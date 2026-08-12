import pytest
from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = pytest.mark.django_db


class TestRegister:
    def test_register_creates_user(self, api_client):
        r = api_client.post("/api/auth/register/", {"username": "newuser", "password": "Sup3r-Secret-Pass!"})
        assert r.status_code == 201
        assert User.objects.filter(username="newuser").exists()

    def test_weak_password_rejected(self, api_client):
        r = api_client.post("/api/auth/register/", {"username": "weak", "password": "123"})
        assert r.status_code == 400

    def test_duplicate_username_rejected(self, api_client, user):
        r = api_client.post("/api/auth/register/", {"username": user.username, "password": "Sup3r-Secret-Pass!"})
        assert r.status_code == 400


class TestLoginLogout:
    def test_login_returns_tokens(self, api_client, user):
        r = api_client.post("/api/auth/login/", {"username": "alice", "password": "Sup3r-Secret-Pass!"})
        assert r.status_code == 200
        assert "access" in r.json() and "refresh" in r.json()

    def test_login_wrong_password_rejected(self, api_client, user):
        r = api_client.post("/api/auth/login/", {"username": "alice", "password": "wrong"})
        assert r.status_code == 401

    def test_logout_blacklists_refresh_token(self, api_client, user):
        r = api_client.post("/api/auth/login/", {"username": "alice", "password": "Sup3r-Secret-Pass!"})
        access, refresh = r.json()["access"], r.json()["refresh"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        r = api_client.post("/api/auth/logout/", {"refresh": refresh})
        assert r.status_code == 205

        r = api_client.post("/api/auth/refresh/", {"refresh": refresh})
        assert r.status_code == 401


class TestMe:
    def test_me_requires_auth(self, api_client):
        assert api_client.get("/api/me/").status_code == 401

    def test_me_returns_current_user(self, auth_client):
        r = auth_client.get("/api/me/")
        assert r.status_code == 200
        assert r.json()["username"] == "alice"
