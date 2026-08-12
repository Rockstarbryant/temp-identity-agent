import pytest
from cryptography.fernet import Fernet
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _test_settings(settings):
    """Ensure every test run has the settings the app requires, regardless of .env."""
    settings.CREDENTIAL_ENCRYPTION_KEY = Fernet.generate_key().decode()
    settings.AGENT_ROUTER_API_KEY = "test-key"
    settings.AGENT_ROUTER_BASE_URL = "https://fake-router.example"
    settings.AGENT_ROUTER_MODEL = "test-model"
    settings.ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture(autouse=True)
def _reset_throttle_cache():
    """
    DRF's rate throttles (auth: 5/min, registration_jobs: 10/hour, etc.)
    are backed by Django's cache, not the DB — pytest-django's per-test
    transaction rollback does NOT reset it. Without this, tests that hit
    a throttled endpoint more than once across the whole run start
    tripping each other's limits, which looks like a flaky test but is
    actually just cross-test state leakage.
    """
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(username="alice", password="Sup3r-Secret-Pass!")


@pytest.fixture
def other_user(db, django_user_model):
    return django_user_model.objects.create_user(username="bob", password="Sup3r-Secret-Pass!")


@pytest.fixture
def auth_client(api_client, user):
    from rest_framework_simplejwt.tokens import RefreshToken

    token = RefreshToken.for_user(user).access_token
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


@pytest.fixture
def other_auth_client(api_client, other_user):
    from rest_framework_simplejwt.tokens import RefreshToken

    token = RefreshToken.for_user(other_user).access_token
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client
