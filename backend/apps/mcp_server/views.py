"""
MCP endpoint (Model Context Protocol, "Streamable HTTP" transport, JSON responses only).

Stateless JSON-RPC 2.0 over POST /mcp/ with `Authorization: Bearer tia_...`. Supports
initialize, ping, tools/list and tools/call, which is all tool-only clients need.
It's implemented directly (no SDK) because the app is WSGI and every call returns quickly.
"""
import json
import logging

from django.http import HttpResponse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.mcp_server.auth import ApiKeyAuthentication
from apps.mcp_server.models import ApiKey
from apps.mcp_server.tools import TOOL_INDEX, TOOLS, ToolError

logger = logging.getLogger("apps.mcp")

SUPPORTED_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]
INSTRUCTIONS = (
    "Registers accounts on websites for the user (email + password sign-in only) and extracts information "
    "from them. Start with register_on_site, then poll get_job until finished. If a job needs a human "
    "(CAPTCHA) or an answer, tell the user and give them the ui_url."
)


def _error(rpc_id, code, message):
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}


def _handle(user, msg: dict):
    """Returns a response dict, or None for notifications."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or "method" not in msg:
        return _error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid request.")
    rpc_id, method, params = msg.get("id"), msg["method"], msg.get("params") or {}
    is_notification = "id" not in msg

    if method == "initialize":
        asked = params.get("protocolVersion")
        version = asked if asked in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
        return {"jsonrpc": "2.0", "id": rpc_id, "result": {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "temp-identity-agent", "version": "1.0.0"},
            "instructions": INSTRUCTIONS,
        }}
    if method.startswith("notifications/") or is_notification:
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rpc_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": [
            {k: t[k] for k in ("name", "description", "inputSchema")} for t in TOOLS
        ]}}
    if method == "tools/call":
        tool = TOOL_INDEX.get(params.get("name"))
        if tool is None:
            return _error(rpc_id, -32602, f"Unknown tool {params.get('name')!r}.")
        args = params.get("arguments") or {}
        try:
            payload, is_error = tool["handler"](user, args), False
        except ToolError as exc:
            payload, is_error = {"error": str(exc)}, True
        except Exception:  # noqa: BLE001 - never leak internals to a remote client
            logger.exception("MCP tool %s failed", tool["name"])
            payload, is_error = {"error": "Internal error."}, True
        AuditLog.objects.create(user=user, action="mcp.tool_called", resource_type="McpTool",
                                resource_id=tool["name"], metadata={"error": is_error})
        return {"jsonrpc": "2.0", "id": rpc_id, "result": {
            "content": [{"type": "text", "text": json.dumps(payload, default=str)}],
            "isError": is_error,
        }}
    return _error(rpc_id, -32601, f"Method not found: {method}")


class McpView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mcp"

    def get(self, request):
        # No server-initiated stream: tell clients to use POST only.
        return HttpResponse(status=405, headers={"Allow": "POST"})

    def delete(self, request):
        return HttpResponse(status=405, headers={"Allow": "POST"})

    def post(self, request):
        try:
            body = json.loads(request.body or b"null")
        except ValueError:
            return Response(_error(None, -32700, "Parse error."), status=status.HTTP_400_BAD_REQUEST)
        if isinstance(body, list):
            replies = [r for r in (_handle(request.user, m) for m in body[:20]) if r is not None]
            return Response(replies) if replies else HttpResponse(status=202)
        reply = _handle(request.user, body)
        return Response(reply) if reply is not None else HttpResponse(status=202)


class ApiKeyListCreateView(APIView):
    """
    GET  /api/api-keys/ — your keys (never the secret)
    POST /api/api-keys/ {"name": "..."} — create one; the full key is returned ONCE
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        keys = ApiKey.objects.filter(user=request.user, revoked_at__isnull=True)
        return Response([{"id": str(k.id), "name": k.name, "prefix": k.prefix,
                          "created_at": k.created_at, "last_used_at": k.last_used_at} for k in keys])

    def post(self, request):
        name = str(request.data.get("name", "")).strip() or "MCP client"
        if ApiKey.objects.filter(user=request.user, revoked_at__isnull=True).count() >= 10:
            return Response({"detail": "You can have at most 10 active keys. Revoke one first."},
                            status=status.HTTP_400_BAD_REQUEST)
        key, raw = ApiKey.create_for(request.user, name)
        AuditLog.objects.create(user=request.user, action="apikey.created", resource_type="ApiKey", resource_id=str(key.id))
        return Response({"id": str(key.id), "name": key.name, "prefix": key.prefix, "key": raw,
                         "created_at": key.created_at, "last_used_at": None}, status=status.HTTP_201_CREATED)


class ApiKeyDetailView(APIView):
    """DELETE /api/api-keys/{id}/ — revoke."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        from django.utils import timezone

        updated = ApiKey.objects.filter(id=pk, user=request.user, revoked_at__isnull=True).update(revoked_at=timezone.now())
        if not updated:
            return Response(status=status.HTTP_404_NOT_FOUND)
        AuditLog.objects.create(user=request.user, action="apikey.revoked", resource_type="ApiKey", resource_id=str(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
