"""
OAuth 2.1 for MCP clients such as claude.ai (MCP authorization spec).

Flow: the client finds us through the 401 `WWW-Authenticate: ... resource_metadata` header,
reads the metadata documents, registers itself (RFC 7591), sends the user to /oauth/authorize,
which hands over to the web app's approval page (that is where the user is signed in). On
approval the client gets a one-time code and swaps it (PKCE S256) at /oauth/token for a
short-lived access token plus a rotating refresh token. Access tokens are ordinary MCP API keys
(kind="oauth", 1 hour), so revoking one in Settings disconnects the client.
"""
import base64
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.mcp_server.models import ApiKey, OAuthClient, OAuthCode, OAuthGrant

ACCESS_TOKEN_SECONDS = 3600
REFRESH_TOKEN_DAYS = 30
CODE_SECONDS = 600
SCOPE = "mcp"
LOOPBACK = {"localhost", "127.0.0.1", "[::1]", "::1"}


def base_url(request) -> str:
    configured = getattr(settings, "BACKEND_PUBLIC_URL", "")
    return configured.rstrip("/") if configured else request.build_absolute_uri("/").rstrip("/")


def _cors(response):
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, MCP-Protocol-Version"
    response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def _oauth_error(error: str, description: str = "", http_status: int = 400):
    body = {"error": error}
    if description:
        body["error_description"] = description
    return _cors(JsonResponse(body, status=http_status))


# --- Discovery documents -----------------------------------------------------------

def protected_resource_metadata(request, *args, **kwargs):
    base = base_url(request)
    return _cors(JsonResponse({
        "resource": f"{base}/mcp/",
        "authorization_servers": [base],
        "bearer_methods_supported": ["header"],
        "scopes_supported": [SCOPE],
        "resource_name": "Temporary Identity Agent",
    }))


def authorization_server_metadata(request, *args, **kwargs):
    base = base_url(request)
    return _cors(JsonResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": [SCOPE],
    }))


# --- Dynamic client registration -------------------------------------------------------

def _valid_redirect_uri(uri) -> bool:
    if not isinstance(uri, str) or len(uri) > 500 or "#" in uri:
        return False
    parsed = urlparse(uri)
    if parsed.scheme == "https" and parsed.hostname:
        return True
    return parsed.scheme == "http" and (parsed.hostname or "") in LOOPBACK


class RegisterView(APIView):
    """POST /oauth/register — RFC 7591 dynamic client registration (public clients only)."""

    authentication_classes: list = []
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "oauth"

    def options(self, request, *args, **kwargs):
        return _cors(HttpResponse(status=204))

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        uris = data.get("redirect_uris")
        if not isinstance(uris, list) or not uris or len(uris) > 5 or not all(_valid_redirect_uri(u) for u in uris):
            return _oauth_error("invalid_redirect_uri", "Provide 1-5 https (or http://localhost) redirect URIs.")
        name = str(data.get("client_name") or "MCP client").strip()[:120] or "MCP client"
        client = OAuthClient.objects.create(client_id=secrets.token_urlsafe(24), name=name, redirect_uris=uris)
        resp = JsonResponse({
            "client_id": client.client_id,
            "client_name": client.name,
            "redirect_uris": uris,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "client_id_issued_at": int(client.created_at.timestamp()),
        }, status=201)
        return _cors(resp)


# --- Authorization -----------------------------------------------------------------------

def _check_authorize_params(params):
    """Returns (client, error). A bad client/redirect is never redirected to."""
    client = OAuthClient.objects.filter(client_id=params.get("client_id", "")).first()
    redirect_uri = params.get("redirect_uri", "")
    if client is None or redirect_uri not in client.redirect_uris:
        return None, "Unknown client or redirect URI."
    return client, ""


def _protocol_error(params) -> str:
    if params.get("response_type", "code") != "code":
        return "unsupported_response_type"
    if not params.get("code_challenge") or params.get("code_challenge_method") != "S256":
        return "invalid_request"  # PKCE with S256 is mandatory
    return ""


def _redirect_with(redirect_uri: str, **query) -> str:
    sep = "&" if "?" in redirect_uri else "?"
    return redirect_uri + sep + urlencode({k: v for k, v in query.items() if v})


class AuthorizeView(APIView):
    """GET /oauth/authorize — validates the request, then sends the user to the web app's approval page."""

    authentication_classes: list = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "oauth"

    def get(self, request):
        params = request.query_params
        client, problem = _check_authorize_params(params)
        if client is None:
            return HttpResponse(problem, status=400, content_type="text/plain")
        err = _protocol_error(params)
        if err:
            return HttpResponseRedirect(_redirect_with(params["redirect_uri"], error=err, state=params.get("state", "")))
        keep = ("client_id", "redirect_uri", "state", "code_challenge", "code_challenge_method", "scope", "resource")
        query = urlencode({k: params[k] for k in keep if params.get(k)})
        return HttpResponseRedirect(f"{settings.FRONTEND_URL}/oauth/authorize?{query}")


class AuthorizeInfoView(APIView):
    """GET /api/oauth/authorize-info/ — what the approval page shows (needs the user's login)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        client, problem = _check_authorize_params(request.query_params)
        if client is None:
            return Response({"detail": problem}, status=status.HTTP_400_BAD_REQUEST)
        if _protocol_error(request.query_params):
            return Response({"detail": "This sign-in request is malformed."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"client_name": client.name, "redirect_host": urlparse(request.query_params["redirect_uri"]).hostname})


class ApproveView(APIView):
    """POST /api/oauth/approve/ — the signed-in user allows (or denies) the client. Returns where to send the browser."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "oauth"

    def post(self, request):
        data = request.data
        client, problem = _check_authorize_params(data)
        if client is None:
            return Response({"detail": problem}, status=status.HTTP_400_BAD_REQUEST)
        state = str(data.get("state", ""))[:500]
        redirect_uri = data["redirect_uri"]
        if not data.get("approve"):
            return Response({"redirect_url": _redirect_with(redirect_uri, error="access_denied", state=state)})
        err = _protocol_error(data)
        if err:
            return Response({"redirect_url": _redirect_with(redirect_uri, error=err, state=state)})
        code = secrets.token_urlsafe(32)
        OAuthCode.objects.create(
            code_hash=OAuthCode.hash(code), user=request.user, client=client, redirect_uri=redirect_uri,
            code_challenge=str(data["code_challenge"])[:128], expires_at=timezone.now() + timedelta(seconds=CODE_SECONDS),
        )
        AuditLog.objects.create(user=request.user, action="oauth.approved", resource_type="OAuthClient",
                                resource_id=client.client_id, metadata={"client": client.name})
        from apps.notifications.models import Notification
        from apps.notifications.service import notify

        notify(request.user, Notification.Kind.CLIENT_CONNECTED, f"{client.name} was connected",
               "It can now start jobs for you. Revoke it in Settings if this wasn't you.", "/settings",
               {"client": client.name})
        return Response({"redirect_url": _redirect_with(redirect_uri, code=code, state=state)})


# --- Tokens -----------------------------------------------------------------------------------

def _issue_tokens(user, client, grant: OAuthGrant | None):
    """New access key + new refresh token; the previous access key (if any) is revoked."""
    now = timezone.now()
    if grant is not None and grant.api_key_id:
        ApiKey.objects.filter(pk=grant.api_key_id, revoked_at__isnull=True).update(revoked_at=now)
    key, access = ApiKey.create_for(
        user, f"{client.name} (sign-in)", kind="oauth", expires_at=now + timedelta(seconds=ACCESS_TOKEN_SECONDS)
    )
    refresh = secrets.token_urlsafe(40)
    if grant is None:
        grant = OAuthGrant(user=user, client=client)
    grant.refresh_hash = OAuthGrant.hash(refresh)
    grant.api_key = key
    grant.expires_at = now + timedelta(days=REFRESH_TOKEN_DAYS)
    grant.save()
    return {
        "access_token": access, "token_type": "Bearer", "expires_in": ACCESS_TOKEN_SECONDS,
        "refresh_token": refresh, "scope": SCOPE,
    }


def _pkce_ok(verifier: str, challenge: str) -> bool:
    if not (43 <= len(verifier) <= 128):
        return False
    digest = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii", "ignore")).digest()).rstrip(b"=").decode()
    return secrets.compare_digest(digest, challenge)


class TokenView(APIView):
    """POST /oauth/token — authorization_code and refresh_token grants (form or JSON body)."""

    authentication_classes: list = []
    permission_classes = [permissions.AllowAny]
    parser_classes = [FormParser, MultiPartParser, JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "oauth"

    def options(self, request, *args, **kwargs):
        return _cors(HttpResponse(status=204))

    def post(self, request):
        data = request.data
        grant_type = str(data.get("grant_type", ""))
        client = OAuthClient.objects.filter(client_id=str(data.get("client_id", ""))).first()
        if client is None:
            return _oauth_error("invalid_client", "Unknown client.", 401)

        if grant_type == "authorization_code":
            return self._code(data, client)
        if grant_type == "refresh_token":
            return self._refresh(data, client)
        return _oauth_error("unsupported_grant_type")

    def _code(self, data, client):
        row = OAuthCode.objects.filter(code_hash=OAuthCode.hash(str(data.get("code", ""))), client=client).first()
        if row is None or row.expires_at <= timezone.now():
            return _oauth_error("invalid_grant", "The code is invalid or expired.")
        # Single use: whoever deletes the row first wins.
        if OAuthCode.objects.filter(pk=row.pk).delete()[0] != 1:
            return _oauth_error("invalid_grant", "The code was already used.")
        if str(data.get("redirect_uri", "")) != row.redirect_uri:
            return _oauth_error("invalid_grant", "redirect_uri does not match.")
        if not _pkce_ok(str(data.get("code_verifier", "")), row.code_challenge):
            return _oauth_error("invalid_grant", "PKCE verification failed.")
        tokens = _issue_tokens(row.user, client, None)
        AuditLog.objects.create(user=row.user, action="oauth.token_issued", resource_type="OAuthClient",
                                resource_id=client.client_id, metadata={"client": client.name})
        return _cors(JsonResponse(tokens, headers={"Cache-Control": "no-store"}))

    def _refresh(self, data, client):
        grant = OAuthGrant.objects.select_related("user", "api_key").filter(
            refresh_hash=OAuthGrant.hash(str(data.get("refresh_token", ""))), client=client
        ).first()
        if (
            grant is None or grant.revoked_at or grant.expires_at <= timezone.now() or not grant.user.is_active
            or (grant.api_key_id and grant.api_key.revoked_at and grant.api_key.expires_at
                and grant.api_key.expires_at > timezone.now())  # revoked by the user in Settings
        ):
            return _oauth_error("invalid_grant", "The refresh token is invalid, expired or revoked.")
        return _cors(JsonResponse(_issue_tokens(grant.user, client, grant), headers={"Cache-Control": "no-store"}))
