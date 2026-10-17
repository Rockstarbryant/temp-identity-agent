"use client";

import { useState } from "react";
import { CheckCircle2, Loader2, Mail, RefreshCw, Unplug } from "lucide-react";
import {
  ApiError, EmailConnection, connectImap, disconnectEmail, getGmailAuthorizeUrl, testEmailConnection,
} from "@/lib/api";
import Section from "./Section";

interface Props {
  connection: EmailConnection;
  onChange: (c: EmailConnection) => void;
  notice?: string | null;
}

export default function EmailCard({ connection, onChange, notice }: Props) {
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
      if (c.ok) setInfo("Connection works.");
      else setError(c.last_error || "The connection no longer works.");
    } catch (err) {
      setError(msg(err, "Could not test the connection."));
    } finally {
      setBusy(null);
    }
  }

  async function disconnect() {
    if (!confirm("Disconnect this email? Permanent-account jobs won't be able to read verification emails until you reconnect.")) return;
    setBusy("disconnect");
    setError(null);
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
      hint="Used only for permanent accounts, so the agent can read verification codes and links. It sees only messages that arrive after a job starts, never your existing inbox."
    >
      {notice && <p className="mb-3 rounded-md bg-blue-50 px-3 py-2 text-xs text-blue-800">{notice}</p>}

      {connection.connected ? (
        <div className="space-y-3">
          <div className="flex items-start gap-2 text-sm">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-600" />
            <div className="min-w-0">
              <p className="break-all font-medium">{connection.address}</p>
              <p className="text-xs text-black/50">
                {connection.kind === "gmail" ? "Connected with Google (read-only)" : `Connected over IMAP (${connection.imap_host})`}
                {connection.last_checked_at && ` · checked ${new Date(connection.last_checked_at).toLocaleString()}`}
              </p>
            </div>
          </div>
          {connection.last_error && <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">{connection.last_error}</p>}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={test}
              disabled={busy !== null}
              className="flex items-center gap-1.5 rounded-md border border-black/15 px-3 py-1.5 text-sm hover:bg-black/5 disabled:opacity-50"
            >
              {busy === "test" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} Test
            </button>
            <button
              onClick={disconnect}
              disabled={busy !== null}
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-black/60 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
            >
              {busy === "disconnect" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Unplug className="h-4 w-4" />} Disconnect
            </button>
          </div>
          {info && <p className="text-xs text-green-700">{info}</p>}
        </div>
      ) : (
        <div className="space-y-5">
          <div>
            <button
              onClick={connectGmail}
              disabled={busy !== null || !connection.gmail_oauth_available}
              className="flex w-full items-center justify-center gap-2 rounded-md border border-black/15 px-3 py-2 text-sm font-medium hover:bg-black/5 disabled:opacity-50 sm:w-auto"
            >
              {busy === "gmail" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
              Connect Gmail with Google
            </button>
            {!connection.gmail_oauth_available && (
              <p className="mt-1.5 text-xs text-black/50">
                Not set up on this server yet (needs a Google Cloud OAuth client). Use an app password below instead.
              </p>
            )}
          </div>

          <form onSubmit={submitImap} className="space-y-3 border-t border-black/10 pt-4">
            <p className="text-xs font-semibold text-black/70">Or use an app password (Gmail, Outlook, Yahoo, iCloud, others)</p>
            <input
              type="email" required value={address} onChange={(e) => setAddress(e.target.value)}
              placeholder="you@gmail.com" autoComplete="email"
              className="w-full rounded-md border border-black/15 px-3 py-2 text-sm"
            />
            <input
              type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="App password" autoComplete="new-password"
              className="w-full rounded-md border border-black/15 px-3 py-2 text-sm"
            />
            {showHost && (
              <input
                value={host} onChange={(e) => setHost(e.target.value)} placeholder="Mail server, e.g. imap.example.com"
                className="w-full rounded-md border border-black/15 px-3 py-2 text-sm"
              />
            )}
            <p className="text-xs text-black/50">
              This is not your normal password. For Gmail, turn on 2-step verification, then create an &ldquo;app
              password&rdquo; in your Google account&apos;s security page. We log in once to check it, and store it
              encrypted.{" "}
              {!showHost && (
                <button type="button" onClick={() => setShowHost(true)} className="underline">
                  Other mail server?
                </button>
              )}
            </p>
            <button
              type="submit" disabled={busy !== null}
              className="flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-60"
            >
              {busy === "imap" && <Loader2 className="h-4 w-4 animate-spin" />} Connect
            </button>
          </form>
        </div>
      )}
      {error && <p className="mt-3 text-xs text-red-600">{error}</p>}
    </Section>
  );
}
