"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Mail } from "lucide-react";
import { useCachedData } from "@/lib/useCachedData";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { VAULT_CACHE_KEY, fetchVault, type VaultData } from "@/lib/vaultData";
import { getEmailConnection, type EmailConnection } from "@/lib/api";
import MailboxPanel, { InboxPanel } from "@/components/MailboxPanel";
import PageHeader from "@/components/ui/PageHeader";
import { EmptyState, ErrorState, PageSpinner } from "@/components/ui/States";
import { buttonClass } from "@/components/ui/Button";
import { inputClass } from "@/components/ui/Field";

const INBOX = "inbox";

/**
 * Two kinds of mailbox. Your connected Gmail / IMAP inbox is ONE inbox for every permanent account
 * (all its mail in one list, one mute switch). Disposable mailboxes belong to one temporary vault
 * account each. This page builds its index from the account list (the same cached data as the
 * Identity Vault) plus the email connection.
 */
function MailboxesInner() {
  const ready = useRequireAuth();
  const router = useRouter();
  const params = useSearchParams();
  const { data, error, loading, refresh } = useCachedData<VaultData>(ready ? VAULT_CACHE_KEY : null, fetchVault);

  const [connection, setConnection] = useState<EmailConnection | null>(null);
  const [connectionLoaded, setConnectionLoaded] = useState(false);
  useEffect(() => {
    if (!ready) return;
    getEmailConnection().then(setConnection).catch(() => setConnection(null)).finally(() => setConnectionLoaded(true));
  }, [ready]);
  const hasInbox = !!connection?.connected;

  // A deleted account has no mailbox any more. Expired accounts keep their saved messages.
  // With a connected inbox, permanent accounts' mail is in that one inbox, so they are not listed separately.
  const accounts = useMemo(
    () => (data?.accounts ?? []).filter((a) => a.status !== "deleted" && !(hasInbox && a.permanent)),
    [data, hasInbox],
  );
  const wanted = params.get("account");
  const wantedIsPermanent = !!wanted && !!data?.accounts.some((a) => a.id === wanted && a.permanent);
  const wantsInbox = hasInbox && (params.get("inbox") === "1" || !wanted || wantedIsPermanent);
  const selected = wantsInbox ? undefined : accounts.find((a) => a.id === wanted) ?? accounts[0];
  const choice = wantsInbox ? INBOX : selected?.id ?? "";

  return (
    <div>
      <PageHeader title="Mailboxes" description="Verification emails: one disposable mailbox per temporary account, and your connected inbox for permanent ones." />

      {!ready || (loading && !error) || !connectionLoaded ? (
        <PageSpinner />
      ) : error && !data ? (
        <ErrorState title="Could not load your accounts" message="Check your connection and try again." onRetry={() => void refresh()} />
      ) : !selected && !wantsInbox ? (
        <EmptyState
          icon={<Mail className="h-4 w-4" aria-hidden="true" />}
          title="No mailboxes yet"
          description="Each account the agent creates gets a mailbox. Start a task and it will appear here."
          action={<Link href="/new" className={buttonClass("primary")}>Start a task</Link>}
        />
      ) : (
        <div className="space-y-5">
          <div className="max-w-md">
            <label htmlFor="mailbox-account" className="mb-1 block text-xs font-medium">Account</label>
            <select
              id="mailbox-account"
              value={choice}
              onChange={(e) => router.replace(e.target.value === INBOX ? "/mailboxes?inbox=1" : `/mailboxes?account=${e.target.value}`)}
              className={inputClass}
            >
              {hasInbox && <option value={INBOX}>Connected inbox · {connection?.address}</option>}
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.domain} · {a.email}{a.status === "expired" ? " (expired)" : ""}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-muted">
              {selected ? (
                <Link href={`/accounts/${selected.id}`} className="text-accent-strong hover:underline">Open this account in the Identity Vault</Link>
              ) : (
                <>Mail for all your permanent accounts, in one place. <Link href="/settings" className="text-accent-strong hover:underline">Email settings</Link></>
              )}
            </p>
          </div>

          <div className="rounded-lg border border-line bg-surface p-4">
            {selected ? <MailboxPanel key={selected.id} accountId={selected.id} /> : <InboxPanel key={INBOX} />}
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
