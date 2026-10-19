"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Copy, ExternalLink, Eye, EyeOff, Loader2, PenLine } from "lucide-react";
import { ApiError, ManualKit as Kit, completeManualSignup, getManualKit } from "@/lib/api";
import { invalidate } from "@/lib/cache";

function Copyable({ value, secret }: { value: string; secret?: boolean }) {
  const [copied, setCopied] = useState(false);
  const [shown, setShown] = useState(!secret);
  return (
    <span className="flex min-w-0 items-center gap-1">
      <code className="min-w-0 break-all rounded bg-black/[0.05] px-1.5 py-0.5 text-xs">
        {shown ? value : "••••••••••••"}
      </code>
      {secret && (
        <button onClick={() => setShown(!shown)} className="rounded p-1 text-black/40 hover:bg-black/5" aria-label={shown ? "Hide" : "Show"}>
          {shown ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
        </button>
      )}
      <button
        onClick={() => {
          navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }}
        className="rounded p-1 text-black/40 hover:bg-black/5 hover:text-accent" aria-label="Copy"
      >
        {copied ? <Check className="h-3.5 w-3.5 text-green-600" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </span>
  );
}

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
      <div className="rounded-md border border-black/10 bg-white p-4 text-sm">
        <p className="flex items-center gap-2 font-medium"><PenLine className="h-4 w-4 text-accent" /> Sign up yourself</p>
        <p className="mt-1 text-xs text-black/60">
          Can&apos;t solve the CAPTCHA? Get the details the agent would have typed, paste them into the site&apos;s own form,
          then save the result to your vault.
        </p>
        <button onClick={open} disabled={loading}
                className="mt-3 flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-60">
          {loading && <Loader2 className="h-4 w-4 animate-spin" />} Show me what to enter
        </button>
        {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      </div>
    );
  }

  const known = kit.fields.filter((f) => f.value);
  const others = kit.fields.filter((f) => !f.value);

  return (
    <div className="space-y-4 rounded-md border border-black/10 bg-white p-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 font-medium"><PenLine className="h-4 w-4 text-accent" /> Fill in the form on {kit.domain}</p>
        <a href={kit.url} target="_blank" rel="noopener noreferrer"
           className="flex items-center gap-1 text-xs font-medium text-accent hover:underline">
          Open the sign-up page <ExternalLink className="h-3 w-3" />
        </a>
      </div>

      {known.length > 0 ? (
        <dl className="divide-y divide-black/10 rounded-md border border-black/10">
          {known.map((f, i) => (
            <div key={i} className="grid gap-1 px-3 py-2 sm:grid-cols-[38%_1fr] sm:items-center sm:gap-3">
              <dt className="text-xs text-black/60">{f.label}{f.required && <span className="text-red-500"> *</span>}</dt>
              <dd><Copyable value={f.value} secret={f.secret} /></dd>
            </div>
          ))}
        </dl>
      ) : (
        <dl className="space-y-2 rounded-md border border-black/10 p-3">
          <div className="flex items-center justify-between gap-2"><dt className="text-xs text-black/60">Email</dt><dd><Copyable value={kit.email} /></dd></div>
          {kit.username && <div className="flex items-center justify-between gap-2"><dt className="text-xs text-black/60">Username</dt><dd><Copyable value={kit.username} /></dd></div>}
          <div className="flex items-center justify-between gap-2"><dt className="text-xs text-black/60">Password</dt><dd><Copyable value={kit.password} secret /></dd></div>
        </dl>
      )}

      {others.length > 0 && (
        <div className="text-xs text-black/60">
          <p className="mb-1 font-medium">The form also asks for (not saved details, choose yourself):</p>
          <ul className="list-inside list-disc space-y-0.5">
            {others.map((f, i) => (
              <li key={i}>
                {f.label}{f.required && <span className="text-red-500"> *</span>}
                {f.options.length > 0 && <span className="text-black/40"> ({f.options.slice(0, 6).join(", ")}{f.options.length > 6 ? "…" : ""})</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="space-y-2 border-t border-black/10 pt-3">
        <p className="text-xs font-medium text-black/70">When you&apos;ve signed up, save it</p>
        <p className="text-xs text-black/50">Changed the username or password on the site? Enter what you actually used. Otherwise leave these blank.</p>
        <div className="grid gap-2 sm:grid-cols-2">
          <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Username used" maxLength={150}
                 className="rounded-md border border-black/15 px-3 py-1.5 text-sm" />
          <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Different password (optional)" type="password"
                 autoComplete="new-password" className="rounded-md border border-black/15 px-3 py-1.5 text-sm" />
        </div>
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note (optional)" maxLength={500}
               className="w-full rounded-md border border-black/15 px-3 py-1.5 text-sm" />
        <button onClick={save} disabled={saving}
                className="flex items-center gap-1.5 rounded-md bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-60">
          {saving && <Loader2 className="h-4 w-4 animate-spin" />} I&apos;ve signed up — save to my vault
        </button>
        <p className="text-[11px] text-black/40">Any verification email will arrive in this account&apos;s mailbox in your vault and you&apos;ll get a notification.</p>
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    </div>
  );
}
