import secrets
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.core import signing
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.common.exceptions import UnsafeURLError
from apps.common.url_safety import validate_url
from apps.email_service.providers.base import EmailProviderError
from apps.email_service.providers.user_imap import open_imap, preset_host
from apps.profiles import standard_fields as sf
from apps.profiles import signin
from apps.profiles.models import ConnectedAccount, EmailConnection, ProfileEntry, UserPreferences

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = "openid email https://www.googleapis.com/auth/gmail.readonly"
STATE_SALT = "gmail-oauth-state"
STATE_MAX_AGE = 600


def _entry_dict(e: ProfileEntry) -> dict:
    return {"key": e.key, "label": e.label, "value": e.get_value(), "source": e.source}


class ProfileView(APIView):
    """GET /api/profile/ — preferences + saved details, in one call for the Settings page."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        prefs = UserPreferences.for_user(request.user)
        entries = ProfileEntry.objects.filter(user=request.user)
        return Response({
            "account_mode": prefs.account_mode,
            "standard_fields": sf.STANDARD_FIELDS,
            "entries": [_entry_dict(e) for e in entries],
        })


class PreferencesView(APIView):
    """PATCH /api/preferences/ — {"account_mode": "temporary" | "permanent"}"""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        mode = request.data.get("account_mode")
        if mode not in UserPreferences.AccountMode.values:
            return Response({"account_mode": "Must be 'temporary' or 'permanent'."}, status=status.HTTP_400_BAD_REQUEST)
        prefs = UserPreferences.for_user(request.user)
        prefs.account_mode = mode
        prefs.save(update_fields=["account_mode", "updated_at"])
        return Response({"account_mode": prefs.account_mode})


class ProfileEntryView(APIView):
    """
    PUT    /api/profile/entries/{key}/ — {"value": "...", "label": "..."}; empty value deletes it.
    DELETE /api/profile/entries/{key}/
    """

    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, key):
        key = sf.normalize_key(key)
        if not key or sf.is_blocked_key(key):
            return Response({"detail": "That detail can't be saved here (passwords and similar secrets are never stored)."},
                            status=status.HTTP_400_BAD_REQUEST)
        value = str(request.data.get("value", "")).strip()
        if not value:
            ProfileEntry.objects.filter(user=request.user, key=key).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        if len(value) > 500:
            return Response({"value": "Too long (500 characters max)."}, status=status.HTTP_400_BAD_REQUEST)
        entry = ProfileEntry.save_value(
            request.user, key, value, label=str(request.data.get("label", ""))[:150], source=ProfileEntry.Source.SETTINGS
        )
        return Response(_entry_dict(entry))

    def delete(self, request, key):
        ProfileEntry.objects.filter(user=request.user, key=sf.normalize_key(key)).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Email connection -----------------------------------------------------------

def _connection_dict(conn: EmailConnection | None) -> dict:
    return {
        "connected": conn is not None,
        "kind": conn.kind if conn else None,
        "address": conn.address if conn else None,
        "imap_host": conn.imap_host if conn else None,
        "last_checked_at": conn.last_checked_at if conn else None,
        "last_error": conn.last_error if conn else "",
        "gmail_oauth_available": bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET
                                      and settings.GOOGLE_OAUTH_REDIRECT_URI),
    }


class EmailConnectionView(APIView):
    """
    GET    /api/email-connection/ — current connection (never includes the secret)
    PUT    /api/email-connection/ — IMAP: {address, password, host?}; logs in once to verify, then saves
    DELETE /api/email-connection/ — disconnect and erase the stored secret
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_connect"

    def get_throttles(self):
        # Only the write (login attempt) is tightly limited.
        return super().get_throttles() if self.request.method == "PUT" else []

    def get(self, request):
        return Response(_connection_dict(EmailConnection.objects.filter(user=request.user).first()))

    def put(self, request):
        address = str(request.data.get("address", "")).strip().lower()
        password = str(request.data.get("password", ""))
        host = str(request.data.get("host", "")).strip().lower() or preset_host(address)
        if "@" not in address or not password:
            return Response({"detail": "Enter your email address and an app password."}, status=status.HTTP_400_BAD_REQUEST)
        if not host:
            return Response({"detail": "Enter your mail server (IMAP host), e.g. imap.example.com."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            # Connecting to a user-supplied host: refuse private/internal addresses.
            validate_url(f"https://{host}")
        except UnsafeURLError:
            return Response({"detail": "That mail server address isn't allowed."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            imap = open_imap(host, 993, address, password)
            imap.logout()
        except EmailProviderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        conn = EmailConnection.objects.filter(user=request.user).first() or EmailConnection(user=request.user)
        conn.kind = EmailConnection.Kind.IMAP
        conn.address, conn.imap_host, conn.imap_port = address, host, 993
        conn.set_secret(password)
        conn.last_checked_at, conn.last_error = timezone.now(), ""
        conn.save()
        AuditLog.objects.create(user=request.user, action="email.connected", resource_type="EmailConnection",
                                resource_id=str(conn.id), metadata={"kind": "imap", "host": host})
        return Response(_connection_dict(conn))

    def delete(self, request):
        EmailConnection.objects.filter(user=request.user).delete()
        AuditLog.objects.create(user=request.user, action="email.disconnected", resource_type="EmailConnection",
                                resource_id=str(request.user.id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmailConnectionTestView(APIView):
    """POST /api/email-connection/test/ — check the saved connection still works."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_connect"

    def post(self, request):
        conn = EmailConnection.objects.filter(user=request.user).first()
        if conn is None:
            return Response({"detail": "No email connected."}, status=status.HTTP_404_NOT_FOUND)
        try:
            if conn.kind == EmailConnection.Kind.IMAP:
                open_imap(conn.imap_host, conn.imap_port, conn.address, conn.get_secret()).logout()
            else:
                from apps.email_service.providers.user_gmail import get_access_token

                get_access_token(conn)
            conn.last_error = ""
            ok = True
        except EmailProviderError as exc:
            conn.last_error = str(exc)[:300]
            ok = False
        conn.last_checked_at = timezone.now()
        conn.save(update_fields=["last_error", "last_checked_at", "updated_at"])
        return Response({"ok": ok, **_connection_dict(conn)})


class GmailAuthorizeView(APIView):
    """GET /api/email-connection/gmail/authorize/ — returns the Google consent URL to send the browser to."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _connection_dict(None)["gmail_oauth_available"]:
            return Response(
                {"detail": "Gmail sign-in isn't set up on this server (missing GOOGLE_OAUTH_* settings). "
                           "Use an app password instead."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        state = signing.dumps({"u": str(request.user.id), "n": secrets.token_urlsafe(8)}, salt=STATE_SALT)
        params = {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": GOOGLE_SCOPES,
            "access_type": "offline",
            "prompt": "consent",  # ensures a refresh token is issued
            "state": state,
        }
        return Response({"url": f"{GOOGLE_AUTH_URL}?{urlencode(params)}"})


def _settings_redirect(**params) -> HttpResponseRedirect:
    return HttpResponseRedirect(f"{settings.FRONTEND_URL}/settings?{urlencode(params)}")


class GmailCallbackView(APIView):
    """
    GET /api/email-connection/gmail/callback/ — Google redirects the browser here.
    Unauthenticated by necessity; the signed, short-lived `state` identifies the user.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    throttle_classes: list = []

    def get(self, request):
        from django.contrib.auth import get_user_model

        if request.GET.get("error"):
            return _settings_redirect(gmail="denied")
        try:
            data = signing.loads(request.GET.get("state", ""), salt=STATE_SALT, max_age=STATE_MAX_AGE)
            user = get_user_model().objects.get(id=data["u"])
        except (signing.BadSignature, get_user_model().DoesNotExist, KeyError):
            return _settings_redirect(gmail="error")

        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(GOOGLE_TOKEN_URL, data={
                    "code": request.GET.get("code", ""),
                    "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                    "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
                    "grant_type": "authorization_code",
                })
                if resp.status_code != 200:
                    return _settings_redirect(gmail="error")
                tokens = resp.json()
                refresh = tokens.get("refresh_token")
                info = client.get("https://openidconnect.googleapis.com/v1/userinfo",
                                  headers={"Authorization": f"Bearer {tokens['access_token']}"})
            address = info.json().get("email", "") if info.status_code == 200 else ""
        except (httpx.HTTPError, KeyError, ValueError):
            return _settings_redirect(gmail="error")
        if not refresh or not address:
            return _settings_redirect(gmail="error")

        conn = EmailConnection.objects.filter(user=user).first() or EmailConnection(user=user)
        conn.kind = EmailConnection.Kind.GMAIL
        conn.address, conn.imap_host = address, ""
        conn.set_secret(refresh)
        conn.last_checked_at, conn.last_error = timezone.now(), ""
        conn.save()
        AuditLog.objects.create(user=user, action="email.connected", resource_type="EmailConnection",
                                resource_id=str(conn.id), metadata={"kind": "gmail"})
        return _settings_redirect(gmail="connected")


# --- Connected Google / Microsoft accounts (for forms that need a sign-in) -----------

def _account_dict(a: ConnectedAccount) -> dict:
    return {
        "provider": a.provider,
        "email": a.email,
        "has_password": a.has_password,
        "signed_in": a.has_session,
        "session_saved_at": a.session_saved_at,
        "last_used_at": a.last_used_at,
        "last_error": a.last_error,
    }


class ConnectedAccountsView(APIView):
    """
    GET /api/connected-accounts/ — the user's accounts (never includes secrets)
    PUT /api/connected-accounts/ — {provider, email, password?}; a blank password keeps the saved one
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_connect"

    def get_throttles(self):
        return super().get_throttles() if self.request.method == "PUT" else []

    def get(self, request):
        return Response([_account_dict(a) for a in ConnectedAccount.objects.filter(user=request.user).order_by("provider")])

    def put(self, request):
        provider = str(request.data.get("provider", ""))
        email = str(request.data.get("email", "")).strip().lower()
        password = str(request.data.get("password", ""))
        if provider not in ConnectedAccount.Provider.values:
            return Response({"detail": "Choose Google or Microsoft."}, status=status.HTTP_400_BAD_REQUEST)
        if "@" not in email or len(email) > 254:
            return Response({"detail": "Enter the account's email address."}, status=status.HTTP_400_BAD_REQUEST)
        if len(password) > 200:
            return Response({"detail": "That password is too long."}, status=status.HTTP_400_BAD_REQUEST)
        account = ConnectedAccount.objects.filter(user=request.user, provider=provider).first() or ConnectedAccount(
            user=request.user, provider=provider
        )
        if account.pk and account.email != email:
            account.set_session(None)  # a different account: the old session no longer applies
            account.set_password("")
        account.email = email
        if password:
            account.set_password(password)
        account.last_error = ""
        account.save()
        AuditLog.objects.create(
            user=request.user, action="connected_account.saved", resource_type="ConnectedAccount",
            resource_id=str(account.id), metadata={"provider": provider},
        )
        return Response(_account_dict(account))


class ConnectedAccountDetailView(APIView):
    """DELETE /api/connected-accounts/{provider}/ — forget the account, its password and its session."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, provider):
        deleted, _ = ConnectedAccount.objects.filter(user=request.user, provider=provider).delete()
        if deleted:
            AuditLog.objects.create(
                user=request.user, action="connected_account.removed", resource_type="ConnectedAccount",
                resource_id=provider, metadata={"provider": provider},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConnectedAccountSignInView(APIView):
    """POST /api/connected-accounts/{provider}/signin/ — start a job that signs in and saves the session."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_connect"

    def post(self, request, provider):
        from apps.registration.jobs import create_job
        from apps.registration.models import RegistrationJob
        from apps.registration.serializers import RegistrationJobSerializer

        if provider not in signin.LOGIN_URLS:
            return Response({"detail": "Unknown provider."}, status=status.HTTP_404_NOT_FOUND)
        if not ConnectedAccount.objects.filter(user=request.user, provider=provider).exists():
            return Response({"detail": "Add the account first."}, status=status.HTTP_400_BAD_REQUEST)
        job = create_job(
            request.user, signin.LOGIN_URLS[provider], kind=RegistrationJob.Kind.ACCOUNT_SETUP,
            goal=provider, audit_extra={"provider": provider},
        )
        return Response(RegistrationJobSerializer(job).data, status=status.HTTP_201_CREATED)
