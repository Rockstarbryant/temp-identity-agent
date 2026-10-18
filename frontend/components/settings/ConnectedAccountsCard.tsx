"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Loader2, LogIn, Plus, Trash2 } from "lucide-react";
import {
  AccountProvider, ApiError, ConnectedAccount, removeConnectedAccount, saveConnectedAccount, startAccountSignIn,
} from "@/lib/api";
import Section from "./Section";

const NAMES: Record<AccountProvider, string> = { google: "Google", microsoft: "Microsoft" };

interface Props {
  accounts: ConnectedAccount[];
  onChange: (accounts: ConnectedAccount[]) => void;
}

export default function ConnectedAccountsCard({ accounts, onChange }: Props) {
  const router = useRouter();
  const [provider, setProvider] = useState<AccountProvider>("google");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const msg = (err: unknown, fallback: string) => {
    if (err instanceof ApiError) {
      const body = err.body as { detail?: string } | undefined;
      return body?.detail || fallback;
    }
    return fallback;
  };

  const upsert = (a: ConnectedAccount) =>
    onChange([...accounts.filter((x) => x.provider !== a.provider), a].sort((x, y) => x.provider.localeCompare(y.provider)));

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setBusy("add");
    setError(null);
    try {
      const a = await saveConnectedAccount(provider, email, password);
      setEmail("");
      setPassword("");
      upsert(a);
    } catch (err) {
      setError(msg(err, "Could not save the account."));
    } finally {
      setBusy(null);
    }
  }

  async function signIn(p: AccountProvider) {
    setBusy(`signin-${p}`);
    setError(null);
    try {
      const job = await startAccountSignIn(p);
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError(msg(err, "Could not start the sign-in."));
      setBusy(null);
    }
  }

  async function remove(p: AccountProvider) {
    if (!confirm(`Remove this ${NAMES[p]} account from the agent? Its saved password and sign-in are erased.`)) return;
    setBusy(`remove-${p}`);
    setError(null);
    try {
      await removeConnectedAccount(p);
      onChange(accounts.filter((a) => a.provider !== p));
    } catch (err) {
      setError(msg(err, "Could not remove the account."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Section
      title="Accounts for forms that need a sign-in"
      hint="Some Google and Microsoft forms only accept signed-in people. Give the agent a separate account made just for this, never your main one. Passwords and sign-ins are encrypted and are never shown to the AI."
    >
      <div className="space-y-4">
        {accounts.map((a) => (
          <div key={a.provider} className="space-y-2 rounded-md border border-black/10 p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-medium uppercase tracking-wide text-black/40">{NAMES[a.provider]}</p>
                <p className="break-all text-sm font-medium">{a.email}</p>
              </div>
              {a.signed_in ? (
                <span className="flex shrink-0 items-center gap-1 rounded-full bg-green-50 px-2.5 py-1 text-xs text-green-700">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Signed in
                </span>
              ) : (
                <span className="shrink-0 rounded-full bg-black/5 px-2.5 py-1 text-xs text-black/55">Not signed in yet</span>
              )}
            </div>
            <p className="text-xs text-black/50">
              {a.has_password ? "Password saved, so the agent can sign in again when needed." : "No password saved: you sign in yourself when asked."}
              {a.session_saved_at && ` · signed in ${new Date(a.session_saved_at).toLocaleString()}`}
            </p>
            {a.last_error && <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">{a.last_error}</p>}
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => signIn(a.provider)} disabled={busy !== null}
                className="flex items-center gap-1.5 rounded-md border border-black/15 px-3 py-1.5 text-sm hover:bg-black/5 disabled:opacity-50"
              >
                {busy === `signin-${a.provider}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
                {a.signed_in ? "Sign in again" : "Sign in now"}
              </button>
              <button
                onClick={() => remove(a.provider)} disabled={busy !== null}
                className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-black/60 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
              >
                {busy === `remove-${a.provider}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />} Remove
              </button>
            </div>
          </div>
        ))}

        <form onSubmit={add} className="space-y-3">
          <p className="text-sm font-medium">{accounts.length ? "Add or update an account" : "Add an account"}</p>
          <div className="flex gap-2">
            {(["google", "microsoft"] as AccountProvider[]).map((p) => (
              <button
                type="button" key={p} onClick={() => setProvider(p)}
                className={`rounded-md border px-3 py-1.5 text-sm ${provider === p ? "border-accent bg-accent/5 font-medium" : "border-black/15 hover:bg-black/5"}`}
              >
                {NAMES[p]}
              </button>
            ))}
          </div>
          <input
            type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder={`${NAMES[provider]} account email`} autoComplete="off"
            className="w-full rounded-md border border-black/15 px-3 py-2 text-sm"
          />
          <input
            type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            placeholder="Password (optional, leave blank to keep the saved one)" autoComplete="new-password"
            className="w-full rounded-md border border-black/15 px-3 py-2 text-sm"
          />
          <p className="text-xs text-black/50">
            Without a password the agent will ask you to sign in through the live browser each time. Google may also ask
            for a verification step; you can complete it there.
          </p>
          <button
            type="submit" disabled={busy !== null || !email}
            className="flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-50"
          >
            {busy === "add" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Save account
          </button>
        </form>
        {error && <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>}
      </div>
    </Section>
  );
}
