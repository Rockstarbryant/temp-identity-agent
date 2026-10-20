"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ExternalLink, Eye, EyeOff, PenLine } from "lucide-react";
import { ApiError, ManualKit as Kit, completeManualSignup, getManualKit } from "@/lib/api";
import { invalidate } from "@/lib/cache";
import { isSafeHttpUrl } from "@/lib/format";
import Button from "@/components/ui/Button";
import CopyButton from "@/components/ui/CopyButton";
import Field from "@/components/ui/Field";
import { InlineMessage } from "@/components/ui/States";

function Copyable({ value, secret, label }: { value: string; secret?: boolean; label: string }) {
  const [shown, setShown] = useState(!secret);
  return (
    <span className="flex min-w-0 items-center gap-1">
      <code className="min-w-0 break-all rounded bg-subtle px-1.5 py-0.5 font-mono text-xs">
        {shown ? value : "••••••••••••"}
      </code>
      {secret && (
        <button
          type="button" onClick={() => setShown(!shown)}
          aria-label={shown ? `Hide ${label}` : `Show ${label}`}
          className="rounded p-1.5 text-muted hover:bg-subtle hover:text-ink"
        >
          {shown ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
        </button>
      )}
      <CopyButton value={value} label={label} />
    </span>
  );
}

/**
 * Sign-up by hand: shows what the agent would have typed so the user can paste it into the
 * site's own form, then saves the result to the vault. The kit includes a password, so it is
 * only fetched when the user asks for it.
 */
export default function ManualKit({ jobId, onSaved }: { jobId: string; onSaved?: () => void }) {
  const [kit, setKit] = useState<Kit | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [note, setNote] = useState("");
  const router = useRouter();

  async function open() {
    setLoading(true);
    setError("");
    try {
      const k = await getManualKit(jobId);
      setKit(k);
      setUsername(k.username);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not prepare the sign-up details.");
    } finally {
      setLoading(false);
    }
  }

  async function save() {
    setSaving(true);
    setError("");
    try {
      const body: { username?: string; password?: string; note?: string } = {};
      if (username.trim() && username !== kit?.username) body.username = username.trim();
      if (password) body.password = password;
      if (note.trim()) body.note = note.trim();
      const r = await completeManualSignup(jobId, body);
      invalidate("accounts");
      invalidate("jobs");
      onSaved?.();
      router.push(`/accounts/${r.account_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save this sign-up.");
    } finally {
      setSaving(false);
    }
  }

  if (!kit) {
    return (
      <section className="rounded-lg border border-line bg-surface p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <PenLine className="h-4 w-4 text-accent" aria-hidden="true" /> Sign up yourself
        </h2>
        <p className="mt-1 text-sm text-muted">
          Get the details the agent would have entered, paste them into the site&apos;s own form, then save the result to your Identity Vault.
        </p>
        <Button className="mt-3" variant="primary" onClick={open} loading={loading}>Show me what to enter</Button>
        {error && <div className="mt-3"><InlineMessage tone="danger">{error}</InlineMessage></div>}
      </section>
    );
  }

  const known = kit.fields.filter((f) => f.value);
  const others = kit.fields.filter((f) => !f.value);

  return (
    <section className="space-y-4 rounded-lg border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <PenLine className="h-4 w-4 text-accent" aria-hidden="true" /> Fill in the form on <span className="font-mono">{kit.domain}</span>
        </h2>
        {isSafeHttpUrl(kit.url) && (
          <a
            href={kit.url} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs font-medium text-accent-strong hover:underline"
          >
            Open the sign-up page <ExternalLink className="h-3 w-3" aria-hidden="true" />
            <span className="sr-only">(opens in a new tab)</span>
          </a>
        )}
      </div>

      {known.length > 0 ? (
        <dl className="divide-y divide-line rounded-md border border-line">
          {known.map((f, i) => (
            <div key={i} className="grid gap-1 px-3 py-2 sm:grid-cols-[38%_1fr] sm:items-center sm:gap-3">
              <dt className="text-xs text-muted">{f.label}{f.required && <span className="text-danger"> *</span>}</dt>
              <dd><Copyable value={f.value} secret={f.secret} label={f.label || "value"} /></dd>
            </div>
          ))}
        </dl>
      ) : (
        <dl className="space-y-2 rounded-md border border-line p-3">
          <div className="flex items-center justify-between gap-2"><dt className="text-xs text-muted">Email</dt><dd><Copyable value={kit.email} label="email" /></dd></div>
          {kit.username && <div className="flex items-center justify-between gap-2"><dt className="text-xs text-muted">Username</dt><dd><Copyable value={kit.username} label="username" /></dd></div>}
          <div className="flex items-center justify-between gap-2"><dt className="text-xs text-muted">Password</dt><dd><Copyable value={kit.password} secret label="password" /></dd></div>
        </dl>
      )}

      {others.length > 0 && (
        <div className="text-xs text-muted">
          <p className="mb-1 font-medium text-ink">The form also asks for these. They are not saved details, so choose them yourself:</p>
          <ul className="list-inside list-disc space-y-0.5">
            {others.map((f, i) => (
              <li key={i}>
                {f.label}{f.required && <span className="text-danger"> *</span>}
                {f.options.length > 0 && <span> ({f.options.slice(0, 6).join(", ")}{f.options.length > 6 ? ", and more" : ""})</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="space-y-3 border-t border-line pt-4">
        <div>
          <h3 className="text-sm font-medium">When you have signed up, save it</h3>
          <p className="mt-0.5 text-xs text-muted">
            If you changed the username or password on the site, enter what you actually used. Otherwise leave these as they are.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Username you used" value={username} onChange={(e) => setUsername(e.target.value)} maxLength={150} />
          <Field
            label="Different password (optional)" type="password" value={password}
            onChange={(e) => setPassword(e.target.value)} autoComplete="new-password"
          />
        </div>
        <Field label="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />
        <Button variant="primary" onClick={save} loading={saving}>I have signed up. Save to my vault</Button>
        <p className="text-xs text-muted">
          Any verification email will arrive in this account&apos;s mailbox, and you will get a notification.
        </p>
        {error && <InlineMessage tone="danger">{error}</InlineMessage>}
      </div>
    </section>
  );
}
