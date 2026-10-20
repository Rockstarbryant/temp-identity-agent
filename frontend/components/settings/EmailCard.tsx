"use client";

import { useState } from "react";
import { CheckCircle2, Mail, RefreshCw, Unplug } from "lucide-react";
import {
  ApiError, EmailConnection, connectImap, disconnectEmail, getGmailAuthorizeUrl, testEmailConnection,
} from "@/lib/api";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import { InlineMessage } from "@/components/ui/States";
import { useConfirm } from "@/components/ui/Feedback";
import { formatDateTime } from "@/lib/format";
import Section from "./Section";

interface Props {
  connection: EmailConnection;
  onChange: (c: EmailConnection) => void;
  notice?: string | null;
}

export default function EmailCard({ connection, onChange, notice }: Props) {
  const confirm = useConfirm();
  const [address, setAddress] = useState("");
  const [password, setPassword] = useState("");
  const [host, setHost] = useState("");
  const [showHost, setShowHost] = useState(false);
  const [busy, setBusy] = useState<"imap" | "gmail" | "test" | "disconnect" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const msg = (err: unknown, fallback: string) => {
    if (err instanceof ApiError) {
      const body = err.body as { detail?: string } | undefined;
      return body?.detail || String(err.message) || fallback;
    }
    return fallback;
  };

  async function submitImap(e: React.FormEvent) {
    e.preventDefault();
    setBusy("imap");
    setError(null);
    setInfo(null);
    try {
      const c = await connectImap(address, password, host);
      setPassword("");
      onChange(c);
    } catch (err) {
      const text = msg(err, "Could not connect.");
      setError(text);
      if (/IMAP host|mail server/i.test(text)) setShowHost(true);
    } finally {
      setBusy(null);
    }
  }

  async function connectGmail() {
    setBusy("gmail");
    setError(null);
    try {
      const { url } = await getGmailAuthorizeUrl();
      window.location.href = url;
    } catch (err) {
      setError(msg(err, "Could not start Google sign-in."));
      setBusy(null);
    }
  }

  async function test() {
    setBusy("test");
    setError(null);
    setInfo(null);
    try {
      const c = await testEmailConnection();
      onChange(c);
      if (c.ok) setInfo("The connection works.");
      else setError(c.last_error || "The connection no longer works.");
    } catch (err) {
      setError(msg(err, "Could not test the connection."));
    } finally {
      setBusy(null);
    }
  }

  async function disconnect() {
    const ok = await confirm({
      title: "Disconnect your email?",
      description: "Tasks that use a permanent identity will not be able to read verification emails until you reconnect. Your stored email credentials are erased.",
      confirmLabel: "Disconnect",
      destructive: true,
    });
    if (!ok) return;
    setBusy("disconnect");
    setError(null);
    setInfo(null);
    try {
      await disconnectEmail();
      onChange({ ...connection, connected: false, kind: null, address: null, imap_host: null, last_error: "" });
    } catch (err) {
      setError(msg(err, "Could not disconnect."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Section
      title="Your email"
      hint="Used only for permanent identities, so the agent can read verification codes and links. It only sees messages that arrive after a task starts, never your existing inbox. This is separate from the disposable mailboxes used for temporary identities."
    >
      {notice && <div className="mb-3"><InlineMessage tone="info">{notice}</InlineMessage></div>}

      {connection.connected ? (
        <div className="space-y-3">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
            <div className="min-w-0">
              <p className="break-all font-mono text-sm">{connection.address}</p>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <Badge tone={connection.last_error ? "danger" : "success"}>{connection.last_error ? "Needs attention" : "Connected"}</Badge>
                <Badge>{connection.kind === "gmail" ? "Google, read-only" : `IMAP (${connection.imap_host})`}</Badge>
              </div>
              {connection.last_checked_at && <p className="mt-1 text-xs text-muted">Last checked {formatDateTime(connection.last_checked_at)}</p>}
            </div>
          </div>
          {connection.last_error && <InlineMessage tone="danger">{connection.last_error}</InlineMessage>}
          {info && <InlineMessage tone="success">{info}</InlineMessage>}
          <div className="flex flex-wrap gap-2">
            <Button onClick={test} loading={busy === "test"} disabled={busy !== null}>
              {busy !== "test" && <RefreshCw className="h-4 w-4" aria-hidden="true" />} Test connection
            </Button>
            <Button variant="danger-ghost" onClick={disconnect} loading={busy === "disconnect"} disabled={busy !== null}>
              {busy !== "disconnect" && <Unplug className="h-4 w-4" aria-hidden="true" />} Disconnect
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-5">
          <div>
            <Button onClick={connectGmail} loading={busy === "gmail"} disabled={busy !== null || !connection.gmail_oauth_available}>
              {busy !== "gmail" && <Mail className="h-4 w-4" aria-hidden="true" />} Connect Gmail with Google
            </Button>
            {!connection.gmail_oauth_available && (
              <p className="mt-1.5 text-xs text-muted">
                Google sign-in is not set up on this server (it needs a Google Cloud OAuth client). Use an app password below instead.
              </p>
            )}
          </div>

          <form onSubmit={submitImap} className="space-y-3 border-t border-line pt-4">
            <h3 className="text-sm font-semibold">Or use an app password</h3>
            <p className="text-xs text-muted">Works with Gmail, Outlook, Yahoo, iCloud and other IMAP providers.</p>
            <Field label="Email address" type="email" required value={address} onChange={(e) => setAddress(e.target.value)} placeholder="you@example.com" autoComplete="email" mono />
            <Field label="App password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
            {showHost && (
              <Field label="Mail server" value={host} onChange={(e) => setHost(e.target.value)} placeholder="imap.example.com" mono />
            )}
            <p className="text-xs text-muted">
              This is not your normal password. For Gmail, turn on 2-step verification, then create an app password in your Google account&apos;s security settings.
              We log in once to check it and store it encrypted. It is never shown again.{" "}
              {!showHost && (
                <button type="button" onClick={() => setShowHost(true)} className="text-accent-strong underline">Other mail server?</button>
              )}
            </p>
            <Button type="submit" variant="primary" loading={busy === "imap"} disabled={busy !== null}>Connect</Button>
          </form>
        </div>
      )}
      {error && !connection.last_error && <div className="mt-3"><InlineMessage tone="danger">{error}</InlineMessage></div>}
      {error && connection.last_error && error !== connection.last_error && <div className="mt-3"><InlineMessage tone="danger">{error}</InlineMessage></div>}
    </Section>
  );
}
