"""
SSRF protection.

Every outbound URL the system will ask Playwright (or httpx) to fetch —
whether it's the initial user-submitted registration URL or a redirect
target encountered mid-navigation — must pass through validate_url()
first. This blocks localhost, private/link-local IP ranges, and cloud
metadata endpoints.

Call validate_url() again after every redirect hop; a URL that was
safe on first submission can redirect to an internal address.
"""
import ipaddress
import socket
from urllib.parse import urlparse

from apps.common.exceptions import UnsafeURLError

_BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
}

# Cloud metadata service IPs (AWS/GCP/Azure/DigitalOcean all use this address)
_BLOCKED_IPS = {
    ipaddress.ip_address("169.254.169.254"),
}


def _is_private_or_reserved(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip in _BLOCKED_IPS
    )


def validate_url(url: str) -> str:
    """
    Validate that `url` is safe to fetch/navigate to.

    Returns the normalized URL on success, raises UnsafeURLError on
    failure. Resolves DNS to catch hostnames that point at internal
    IPs (DNS rebinding style attacks), not just literal IP URLs.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(f"Unsupported URL scheme: {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError("URL has no hostname.")

    if hostname.lower() in _BLOCKED_HOSTNAMES:
        raise UnsafeURLError(f"Access to '{hostname}' is not allowed.")

    try:
        # Literal IP in the URL
        ip = ipaddress.ip_address(hostname)
        if _is_private_or_reserved(ip):
            raise UnsafeURLError(f"Access to private/internal address '{hostname}' is not allowed.")
    except ValueError:
        # Not a literal IP — resolve DNS and check every resolved address
        try:
            resolved = socket.getaddrinfo(hostname, None)
        except socket.gaierror as exc:
            raise UnsafeURLError(f"Could not resolve hostname '{hostname}'.") from exc

        for family, _, _, _, sockaddr in resolved:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if _is_private_or_reserved(ip):
                raise UnsafeURLError(
                    f"Hostname '{hostname}' resolves to a private/internal address."
                )

    return url
