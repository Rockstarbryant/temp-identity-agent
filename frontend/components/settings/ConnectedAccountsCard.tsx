"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LogIn, Plus, Trash2 } from "lucide-react";
import {
  AccountProvider, ApiError, ConnectedAccount, removeConnectedAccount, saveConnectedAccount, startAccountSignIn,
} from "@/lib/api";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import { InlineMessage } from "@/components/ui/States";
import { useConfirm } from "@/components/ui/Feedback";
import { cn } from "@/components/ui/cn";
import { formatDateTime } from "@/lib/format";
import Section from "./Section";

const NAMES: Record<AccountProvider, string> = { google: "Google", microsoft: "Microsoft" };

interface Props {
  accounts: ConnectedAccount[];
  onChange: (accounts: ConnectedAccount[]) => void;
}

export default function ConnectedAccountsCard({ accounts, onChange }: Props) {
  const router = useRouter();
  const confirm = useConfirm();
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
    const ok = await confirm({
      title: `Remove the ${NAMES[p]} account?`,
      description: "Its saved password and sign-in session are erased from this app. The account itself is not deleted at " + NAMES[p] + ".",
      confirmLabel: "Remove",
      destructive: true,
    });
    if (!ok) return;
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
      hint="Some Google and Microsoft forms only accept signed-in people. Give the agent a separate account made just for this, never your main one. Passwords and sessions are encrypted and never shown to the AI. These are not the temporary identities the agent creates, and they are not your email connection."
    >
      <div className="space-y-4">
        {accounts.map((a) => (
          <div key={a.provider} className="space-y-2.5 rounded-md border border-line p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-medium text-muted">{NAMES[a.provider]}</p>
                <p className="break-all font-mono text-sm">{a.email}</p>
              </div>
              <Badge tone={a.signed_in ? "success" : "neutral"}>{a.signed_in ? "Signed in" : "Not signed in"}</Badge>
            </div>
            <p className="text-xs text-muted">
              {a.has_password ? "A password is saved, so the agent can sign in again when needed." : "No password saved. You sign in yourself when asked."}
              {a.session_saved_at && ` Signed in ${formatDateTime(a.session_saved_at)}.`}
            </p>
            {a.last_error && <InlineMessage tone="warning">{a.last_error}</InlineMessage>}
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void signIn(a.provider)} loading={busy === `signin-${a.provider}`} disabled={busy !== null}>
                {busy !== `signin-${a.provider}` && <LogIn className="h-4 w-4" aria-hidden="true" />}
                {a.signed_in ? "Sign in again" : "Sign in now"}
              </Button>
              <Button variant="danger-ghost" onClick={() => void remove(a.provider)} loading={busy === `remove-${a.provider}`} disabled={busy !== null}>
                {busy !== `remove-${a.provider}` && <Trash2 className="h-4 w-4" aria-hidden="true" />} Remove
              </Button>
            </div>
          </div>
        ))}

        <form onSubmit={add} className="space-y-3">
          <h3 className="text-sm font-semibold">{accounts.length ? "Add or update an account" : "Add an account"}</h3>
          <div role="radiogroup" aria-label="Provider" className="flex gap-2">
            {(["google", "microsoft"] as AccountProvider[]).map((p) => (
              <button
                type="button" key={p} role="radio" aria-checked={provider === p} onClick={() => setProvider(p)}
                className={cn(
                  "rounded-md border px-3 py-1.5 text-sm transition-colors",
                  provider === p ? "border-accent bg-accent-soft font-medium" : "border-line-strong hover:bg-subtle",
                )}
              >
                {NAMES[p]}
              </button>
            ))}
          </div>
          <Field label={`${NAMES[provider]} account email`} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" mono />
          <Field
            label="Password (optional)" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password" hint="Leave blank to keep the saved password. Without one, you sign in yourself in the browser preview each time."
          />
          <Button type="submit" variant="primary" loading={busy === "add"} disabled={busy !== null || !email}>
            {busy !== "add" && <Plus className="h-4 w-4" aria-hidden="true" />} Save account
          </Button>
        </form>
        {error && <InlineMessage tone="danger">{error}</InlineMessage>}
      </div>
    </Section>
  );
}
