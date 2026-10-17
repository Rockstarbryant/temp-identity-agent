"""Runs a real Chromium (skipped when none is installed) to prove the SSRF request guard works."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import pytest

from apps.common.exceptions import UnsafeURLError
from apps.registration.models import RegistrationJob, TargetWebsite

pytestmark = pytest.mark.django_db


class _Handler(BaseHTTPRequestHandler):
    hits = []

    def do_GET(self):
        _Handler.hits.append(self.path)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"internal secret")

    def log_message(self, *a):
        pass


def test_requests_to_internal_addresses_are_blocked(user):
    from apps.browser.playwright_client import ManagedBrowserSession

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _Handler.hits.clear()
    site = TargetWebsite.objects.create(domain="example.com", registration_url="https://example.com")
    job = RegistrationJob.objects.create(user=user, target_website=site)

    def fake_validate(url):
        if "127.0.0.1" in url:
            raise UnsafeURLError("blocked")
        return url

    try:
        with patch("apps.browser.playwright_client.validate_url", side_effect=fake_validate):
            try:
                session = ManagedBrowserSession(job).__enter__()
            except Exception as exc:  # noqa: BLE001
                pytest.skip(f"No usable Chromium here: {exc}")
            try:
                port = server.server_address[1]
                failed = []
                session.page.on("requestfailed", lambda r: failed.append(r.url))
                session.page.set_content(f'<img src="http://127.0.0.1:{port}/steal.png"><p>hi</p>')
                session.page.wait_for_timeout(500)
                assert _Handler.hits == []  # the internal server never saw a request
                assert any("steal.png" in u for u in failed)
                size = session.page.viewport_size
                assert size["width"] == 1024 and size["height"] == 768
            finally:
                session.__exit__(None, None, None)
    finally:
        server.shutdown()
