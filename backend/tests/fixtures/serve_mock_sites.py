#!/usr/bin/env python
"""
Serves backend/tests/fixtures/mock_sites/ over plain HTTP for
Playwright-driven browser tests to navigate to. Deliberately NOT part
of the Django app — these are static fixtures, not application code.

Usage:
    python backend/tests/fixtures/serve_mock_sites.py [port]

Then e.g. http://localhost:8899/simple_registration.html
"""
import http.server
import sys
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "mock_sites"


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
        *args, directory=str(FIXTURES_DIR), **kwargs
    )
    server = http.server.HTTPServer(("127.0.0.1", port), handler)
    print(f"Serving mock registration sites from {FIXTURES_DIR} at http://127.0.0.1:{port}/")
    print("Pages: simple_registration.html, email_verification_registration.html,")
    print("       multi_step_registration_1.html, failing_registration.html,")
    print("       captcha_registration.html, unexpected_structure.html")
    server.serve_forever()


if __name__ == "__main__":
    main()
