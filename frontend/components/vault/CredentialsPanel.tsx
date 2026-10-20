"use client";

import { useEffect, useRef, useState } from "react";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { RevealedCredentials, TemporaryAccountSummary, revealCredentials } from "@/lib/api";
import CopyButton from "@/components/ui/CopyButton";
import Button from "@/components/ui/Button";
import { InlineMessage } from "@/components/ui/States";

const AUTO_HIDE_MS = 60_000;

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 px-4 py-3 sm:grid-cols-[8rem_1fr] sm:items-center sm:gap-4">
      <dt className="text-xs font-medium text-muted">{label}</dt>
      <dd className="flex min-w-0 items-center gap-1">{children}</dd>
    </div>
  );
}

/**
 * Email, username and password for one vault account. The password is not loaded until the
 * user presses Reveal, is shown only on that action, and is dropped from memory again when
 * hidden or after a minute. Credentials are never rendered for deleted or removed accounts.
 */
export default function CredentialsPanel({ account }: { account: TemporaryAccountSummary }) {
  const [revealed, setRevealed] = useState<RevealedCredentials | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const usable = account.status === "active";

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  // A different account, or one that stops being usable, must never keep showing a password.
  useEffect(() => {
    setRevealed(null);
    setError(null);
  }, [account.id, usable]);

  function hide() {
    if (timer.current) clearTimeout(timer.current);
    setRevealed(null);
  }

  async function reveal() {
    setBusy(true);
    setError(null);
    try {
      const creds = await revealCredentials(account.id);
      setRevealed(creds);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setRevealed(null), AUTO_HIDE_MS);
    } catch {
      setError("Could not reveal the password. It was not shown. Try again in a moment.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <dl className="divide-y divide-line rounded-lg border border-line bg-surface">
        <Row label="Email">
          <span className="min-w-0 break-all font-mono text-sm">{account.email}</span>
          <CopyButton value={account.email} label="email address" />
        </Row>
        {account.username && (
          <Row label="Username">
            <span className="min-w-0 break-all font-mono text-sm">{account.username}</span>
            <CopyButton value={account.username} label="username" />
          </Row>
        )}
        <Row label="Password">
          {!usable ? (
            <span className="text-sm text-muted">Not available. This account is {account.status}.</span>
          ) : revealed ? (
            <>
              <span className="min-w-0 break-all font-mono text-sm">{revealed.password}</span>
              <CopyButton value={revealed.password} label="password" />
              <Button size="sm" variant="ghost" onClick={hide} aria-label="Hide password">
                <EyeOff className="h-4 w-4" aria-hidden="true" /> Hide
              </Button>
            </>
          ) : (
            <>
              <span className="font-mono text-sm tracking-widest text-muted" aria-label="Password hidden">••••••••••••</span>
              <Button size="sm" onClick={reveal} disabled={busy}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                Reveal
              </Button>
            </>
          )}
        </Row>
      </dl>
      {revealed && (
        <p className="mt-2 text-xs text-muted">The password hides itself again after a minute. Each reveal is recorded in your audit log.</p>
      )}
      {error && <div className="mt-2"><InlineMessage tone="danger">{error}</InlineMessage></div>}
    </div>
  );
}
