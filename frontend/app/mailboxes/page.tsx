"use client";

import Link from "next/link";
import { Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Mail } from "lucide-react";
import { useCachedData } from "@/lib/useCachedData";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { VAULT_CACHE_KEY, fetchVault, type VaultData } from "@/lib/vaultData";
import MailboxPanel from "@/components/MailboxPanel";
import PageHeader from "@/components/ui/PageHeader";
import { EmptyState, ErrorState, PageSpinner } from "@/components/ui/States";
import { buttonClass } from "@/components/ui/Button";
import { inputClass } from "@/components/ui/Field";

/**
 * There is no global mailbox endpoint: every mailbox belongs to a vault account. This page
 * builds its index from the account list (the same cached data as the Identity Vault) and
 * opens one account's mailbox at a time.
 */
function MailboxesInner() {
  const ready = useRequireAuth();
  const router = useRouter();
  const params = useSearchParams();
  const { data, error, loading, refresh } = useCachedData<VaultData>(ready ? VAULT_CACHE_KEY : null, fetchVault);

  // A deleted account has no mailbox any more. Expired accounts keep their saved messages.
  const accounts = useMemo(() => (data?.accounts ?? []).filter((a) => a.status !== "deleted"), [data]);
  const wanted = params.get("account");
  const selected = accounts.find((a) => a.id === wanted) ?? accounts[0];

  return (
    <div>
      <PageHeader title="Mailboxes" description="Verification emails for the accounts in your Identity Vault." />

      {!ready || (loading && !error) ? (
        <PageSpinner />
      ) : error && !data ? (
        <ErrorState title="Could not load your accounts" message="Check your connection and try again." onRetry={() => void refresh()} />
      ) : !selected ? (
        <EmptyState
          icon={<Mail className="h-4 w-4" aria-hidden="true" />}
          title="No mailboxes yet"
          description="Each account the agent creates gets a mailbox. Start a task and it will appear here."
          action={<Link href="/" className={buttonClass("primary")}>Start a task</Link>}
        />
      ) : (
        <div className="space-y-5">
          <div className="max-w-md">
            <label htmlFor="mailbox-account" className="mb-1 block text-xs font-medium">Account</label>
            <select
              id="mailbox-account"
              value={selected.id}
              onChange={(e) => router.replace(`/mailboxes?account=${e.target.value}`)}
              className={inputClass}
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.domain} · {a.email}{a.status === "expired" ? " (expired)" : ""}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-muted">
              <Link href={`/accounts/${selected.id}`} className="text-accent-strong hover:underline">Open this account in the Identity Vault</Link>
            </p>
          </div>

          <div className="rounded-lg border border-line bg-surface p-4">
            <MailboxPanel key={selected.id} accountId={selected.id} />
          </div>
        </div>
      )}
    </div>
  );
}

export default function MailboxesPage() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <MailboxesInner />
    </Suspense>
  );
}
