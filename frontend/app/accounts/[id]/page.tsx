"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getAccount, revealCredentials, deleteAccount,
  TemporaryAccountSummary, RevealedCredentials, isAuthenticated,
} from "@/lib/api";
import { Loader2, Copy, Check, Eye, Trash2 } from "lucide-react";

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="rounded-md p-1.5 text-black/40 hover:bg-black/5 hover:text-accent"
      aria-label="Copy"
    >
      {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
    </button>
  );
}

export default function AccountDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [account, setAccount] = useState<TemporaryAccountSummary | null>(null);
  const [revealed, setRevealed] = useState<RevealedCredentials | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push(`/login?next=/accounts/${id}`);
      return;
    }
    getAccount(id).then(setAccount).catch(() => setAccount(null));
  }, [id, router]);

  async function handleReveal() {
    setLoading(true);
    setError(null);
    try {
      setRevealed(await revealCredentials(id));
    } catch {
      setError("Could not reveal credentials for this account.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    if (!confirm("Delete this account? This permanently removes the stored credentials.")) return;
    setLoading(true);
    try {
      await deleteAccount(id);
      router.push("/accounts");
    } catch {
      setError("Could not delete this account.");
    } finally {
      setLoading(false);
    }
  }

  if (!account) {
    return <div className="flex justify-center py-16 text-black/40"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  }

  return (
    <div className="mx-auto max-w-md space-y-6">
      <div>
        <h1 className="text-xl font-semibold">{account.domain}</h1>
        <p className="text-xs text-black/40">Expires {new Date(account.expires_at).toLocaleString()}</p>
      </div>

      <dl className="space-y-3 rounded-md border border-black/10 p-4 text-sm">
        <div className="flex items-center justify-between">
          <dt className="text-black/50">Email</dt>
          <dd className="flex items-center gap-1 font-mono">{account.email} <CopyButton value={account.email} /></dd>
        </div>
        {account.username && (
          <div className="flex items-center justify-between">
            <dt className="text-black/50">Username</dt>
            <dd className="flex items-center gap-1 font-mono">{account.username} <CopyButton value={account.username} /></dd>
          </div>
        )}
        <div className="flex items-center justify-between">
          <dt className="text-black/50">Password</dt>
          {revealed ? (
            <dd className="flex items-center gap-1 font-mono">{revealed.password} <CopyButton value={revealed.password} /></dd>
          ) : (
            <dd>
              <button
                onClick={handleReveal} disabled={loading || account.status !== "active"}
                className="flex items-center gap-1 rounded-md bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent/90 disabled:opacity-50"
              >
                {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Eye className="h-3 w-3" />}
                Reveal
              </button>
            </dd>
          )}
        </div>
      </dl>

      {account.status !== "active" && (
        <p className="text-sm text-black/50">This account is {account.status} and can no longer be used.</p>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <button
        onClick={handleDelete} disabled={loading}
        className="flex items-center gap-1 text-sm text-red-600 hover:text-red-700 disabled:opacity-50"
      >
        <Trash2 className="h-4 w-4" /> Delete this account
      </button>
    </div>
  );
}
