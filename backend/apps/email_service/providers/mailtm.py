"""
mail.tm provider — https://docs.mail.tm

No API key required. Workflow:
  1. GET  /domains                 -> pick an available domain
  2. POST /accounts {address, password} -> create the mailbox
  3. POST /token    {address, password} -> {id, token}  (JWT, bearer auth)
  4. GET  /messages                -> Hydra-collection listing (paginated,
                                       "hydra:member" holds the array)
  5. GET  /messages/{id}           -> full message, including `text` and
                                       `html` (mail.tm returns `html` as a
                                       list of HTML fragments)

Rate limit: 8 requests/second per IP (mail.tm's stated general quota).
This provider does not implement its own client-side rate limiting —
callers issuing bursts of requests (e.g. many concurrent jobs) should
throttle at the Celery task level.
"""
import secrets
import string
import time

import httpx
from django.conf import settings

from apps.email_service.providers.base import EmailProvider, EmailProviderError
from apps.email_service.schemas import MessageDetail, MessageSummary, ProvisionedMailbox
from apps.identities.password_generator import generate_password


class MailTmProvider(EmailProvider):
    name = "mailtm"

    def __init__(self, base_url: str | None = None, timeout: float = 15.0):
        self.base_url = (base_url or settings.EMAIL_API_BASE_URL).rstrip("/")
        self.timeout = timeout

    def _client(self, token: str | None = None) -> httpx.Client:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return httpx.Client(base_url=self.base_url, headers=headers, timeout=self.timeout)

    def _get_domain(self, client: httpx.Client) -> str:
        resp = client.get("/domains")
        if resp.status_code != 200:
            raise EmailProviderError(f"mail.tm /domains failed: {resp.status_code} {resp.text}")
        members = resp.json().get("hydra:member", [])
        if not members:
            raise EmailProviderError("mail.tm returned no available domains.")
        return members[0]["domain"]

    def create_mailbox(self, local_part: str | None = None) -> ProvisionedMailbox:
        with self._client() as client:
            domain = self._get_domain(client)
            # Letters and digits only: generate_password() fills spare slots from
            # the full pool (symbols included), which produced invalid addresses
            # like "x9tn*7(9l9$l@..." roughly half the time.
            local_part = local_part or "".join(
                secrets.choice(string.ascii_lowercase + string.digits) for _ in range(12)
            )
            address = f"{local_part}@{domain}"
            # mail.tm requires the account password to satisfy its own
            # minimum length; we generate a strong one and store it via
            # the credential field (encrypted) same as the JWT below.
            account_password = generate_password(
                length=16, min_upper=2, min_lower=2, min_digits=2, min_symbols=2
            )

            resp = client.post("/accounts", json={"address": address, "password": account_password})
            if resp.status_code not in (201, 200):
                raise EmailProviderError(
                    f"mail.tm account creation failed: {resp.status_code} {resp.text}"
                )
            account = resp.json()

            token_resp = client.post("/token", json={"address": address, "password": account_password})
            if token_resp.status_code != 200:
                raise EmailProviderError(
                    f"mail.tm token request failed: {token_resp.status_code} {token_resp.text}"
                )
            token = token_resp.json()["token"]

        return ProvisionedMailbox(
            address=address,
            provider=self.name,
            credential=token,
            provider_account_id=account.get("id", ""),
        )

    def get_messages(self, credential: str) -> list[MessageSummary]:
        with self._client(token=credential) as client:
            resp = client.get("/messages")
            if resp.status_code != 200:
                raise EmailProviderError(f"mail.tm /messages failed: {resp.status_code} {resp.text}")
            members = resp.json().get("hydra:member", [])

        summaries = []
        for m in members:
            summaries.append(
                MessageSummary(
                    external_id=m["id"],
                    sender=(m.get("from") or {}).get("address", ""),
                    subject=m.get("subject", ""),
                    received_at=m.get("createdAt"),
                    seen=m.get("seen", False),
                )
            )
        return summaries

    def get_message(self, credential: str, external_id: str) -> MessageDetail:
        with self._client(token=credential) as client:
            resp = client.get(f"/messages/{external_id}")
            if resp.status_code != 200:
                raise EmailProviderError(
                    f"mail.tm /messages/{external_id} failed: {resp.status_code} {resp.text}"
                )
            m = resp.json()

        html = m.get("html", "")
        # mail.tm returns `html` as a list of HTML fragments, not a string.
        if isinstance(html, list):
            html = "\n".join(html)

        return MessageDetail(
            external_id=m["id"],
            sender=(m.get("from") or {}).get("address", ""),
            subject=m.get("subject", ""),
            text_body=m.get("text", "") or "",
            html_body=html or "",
            received_at=m.get("createdAt"),
        )

    def wait_for_message(
        self, credential: str, timeout_seconds: int = 60, poll_interval_seconds: float = 3.0
    ) -> MessageDetail | None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            messages = self.get_messages(credential)
            if messages:
                return self.get_message(credential, messages[0].external_id)
            time.sleep(poll_interval_seconds)
        return None
