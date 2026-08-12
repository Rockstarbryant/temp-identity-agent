#!/usr/bin/env python
"""
Live smoke test against the REAL mail.tm API — run this yourself, not
in Claude's sandbox (its network egress doesn't include api.mail.tm).

Usage:
    cd backend
    python ../scripts/live_smoke_test_mailtm.py

Provisions a real disposable mailbox, prints the address, then polls
it for up to 60s. Send it a test email from anywhere in that window to
see the full pipeline (fetch -> parse -> extract) run against a real
message.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django  # noqa: E402

django.setup()

from apps.email_service.providers.mailtm import MailTmProvider  # noqa: E402


def main():
    provider = MailTmProvider()

    print("Fetching domains + creating a real mailbox...")
    mailbox = provider.create_mailbox()
    print(f"Mailbox address: {mailbox.address}")
    print(f"Provider account id: {mailbox.provider_account_id}")
    print("\nSend a test email to this address now.")
    print("Polling for up to 60 seconds...\n")

    message = provider.wait_for_message(mailbox.credential, timeout_seconds=60)
    if message is None:
        print("No message arrived within 60s. (Mailbox still exists — mail.tm "
              "mailboxes persist for a while; you can extend the timeout and rerun.)")
        return

    print(f"Received: subject={message.subject!r} from={message.sender!r}")
    link = provider.extract_verification_link(message)
    otp = provider.extract_otp(message)
    print(f"Extracted verification link: {link}")
    print(f"Extracted OTP: {otp}")


if __name__ == "__main__":
    main()
