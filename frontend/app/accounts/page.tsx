"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { KeyRound, Mail, Search } from "lucide-react";
import type { TemporaryAccountSummary } from "@/lib/api";
import { VAULT_CACHE_KEY, fetchVault, type VaultData } from "@/lib/vaultData";
import { useCachedData } from "@/lib/useCachedData";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { describeExpiry } from "@/lib/format";
import PageHeader from "@/components/ui/PageHeader";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/States";
import { buttonClass } from "@/components/ui/Button";
import { inputClass } from "@/components/ui/Field";
import { cn } from "@/components/ui/cn";
import { AccountStatusBadge, AccountTypeBadges } from "@/components/vault/AccountBadges";

export default function IdentityVaultPage() {
  const ready = useRequireAuth();
  const { data, error, loading, refresh } = useCachedData<VaultData>(ready ? VAULT_CACHE_KEY : null, fetchVault);
  const [query, setQuery] = useState("");

  const accounts: TemporaryAccountSummary[] = useMemo(
    () => (data?.accounts ?? []).filter((a) => a.status !== "deleted"),
    [data],
  );
  const removedCount = (data?.accounts.length ?? 0) - accounts.length;
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return accounts;
    return accounts.filter((a) => `${a.domain} ${a.email} ${a.username}`.toLowerCase().includes(q));
  }, [accounts, query]);

  return (
    <div>
      <PageHeader
        title="Identity Vault"
        description="Accounts the agent created for you. Passwords stay hidden until you choose to reveal them."
      />

      {!ready || (loading && !error) ? (
        <ListSkeleton />
      ) : error && !data ? (
        <ErrorState title="Could not load your vault" message="Check your connection and try again." onRetry={() => void refresh()} />
      ) : accounts.length === 0 ? (
        <EmptyState
          icon={<KeyRound className="h-4 w-4" aria-hidden="true" />}
          title="No accounts in your vault"
          description="When a registration task completes, the account and its credentials are saved here."
          action={<Link href="/new" className={buttonClass("primary")}>Start a task</Link>}
        />
      ) : (
        <>
          {accounts.length > 6 && (
            <div className="relative mb-4 max-w-sm">
              <label htmlFor="vault-search" className="sr-only">Search accounts</label>
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden="true" />
              <input
                id="vault-search" type="search" value={query} onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by website or email" className={cn(inputClass, "pl-9")}
              />
            </div>
          )}
          {shown.length === 0 ? (
            <EmptyState title="No accounts match your search" />
          ) : (
            <ul className="grid gap-3 sm:grid-cols-2">
              {shown.map((acct) => {
                const expiry = describeExpiry(acct);
                return (
                  <li key={acct.id} className="flex flex-col rounded-lg border border-line bg-surface">
                    <Link href={`/accounts/${acct.id}`} className="flex-1 rounded-t-lg p-4 hover:bg-subtle">
                      <span className="flex items-start justify-between gap-2">
                        <span className="min-w-0 truncate font-mono text-sm font-medium">{acct.domain}</span>
                        <AccountStatusBadge status={acct.status} />
                      </span>
                      <span className="mt-1 block truncate font-mono text-xs text-muted" title={acct.email}>{acct.email}</span>
                      <span className="mt-3 flex flex-wrap items-center gap-1.5">
                        <AccountTypeBadges account={acct} />
                      </span>
                      <span className={cn("mt-2 block text-xs", expiry.tone === "expired" ? "text-muted" : "text-muted")}>
                        {expiry.label}
                      </span>
                    </Link>
                    <div className="flex items-center justify-between gap-2 border-t border-line px-4 py-2 text-xs">
                      <Link href={`/accounts/${acct.id}`} className="font-medium text-accent-strong hover:underline">
                        View credentials<span className="sr-only"> for {acct.domain}</span>
                      </Link>
                      <Link href={`/mailboxes?account=${acct.id}`} className="inline-flex items-center gap-1 text-muted hover:text-ink">
                        <Mail className="h-3.5 w-3.5" aria-hidden="true" /> Mailbox<span className="sr-only"> for {acct.domain}</span>
                      </Link>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          {data && data.total > data.accounts.length && (
            <p className="mt-3 text-xs text-muted">Showing the {data.accounts.length} most recent of {data.total} accounts.</p>
          )}
          {removedCount > 0 && (
            <p className="mt-3 text-xs text-muted">{removedCount} removed {removedCount === 1 ? "account is" : "accounts are"} hidden.</p>
          )}
        </>
      )}
    </div>
  );
}
