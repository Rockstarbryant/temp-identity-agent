"use client";

import Link from "next/link";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Mail, Trash2 } from "lucide-react";
import { ApiError, deleteAccount, getAccount } from "@/lib/api";
import { invalidate } from "@/lib/cache";
import { useCachedData } from "@/lib/useCachedData";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { describeExpiry, formatDateTime } from "@/lib/format";
import MailboxPanel from "@/components/MailboxPanel";
import AccountChat from "@/components/vault/AccountChat";
import CredentialsPanel from "@/components/vault/CredentialsPanel";
import { AccountStatusBadge, AccountTypeBadges } from "@/components/vault/AccountBadges";
import Button, { buttonClass } from "@/components/ui/Button";
import { Panel } from "@/components/ui/Card";
import { EmptyState, ErrorState, InlineMessage, PageSpinner } from "@/components/ui/States";
import { useConfirm, useToast } from "@/components/ui/Feedback";

export default function AccountDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const ready = useRequireAuth();
  const confirm = useConfirm();
  const toast = useToast();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: account, error: loadError, refresh } = useCachedData(ready ? `account:${id}` : null, () => getAccount(id));

  if (!ready) return <PageSpinner />;
  if (!account) {
    if (loadError instanceof ApiError && loadError.status === 404) {
      return (
        <EmptyState
          title="Account not found"
          description="It may have been removed from your vault."
          action={<Link href="/accounts" className={buttonClass("primary")}>Back to Identity Vault</Link>}
        />
      );
    }
    if (loadError) return <ErrorState title="Could not load this account" message="Check your connection and try again." onRetry={() => void refresh()} />;
    return <PageSpinner label="Loading account" />;
  }

  const expiry = describeExpiry(account);
  const gone = account.status === "deleted";

  async function handleDelete() {
    const ok = await confirm({
      title: `Delete ${account?.domain} from your vault?`,
      description: (
        <>
          <p>This erases the stored password and the mailbox and its messages from this app. It cannot be undone.</p>
          <p className="mt-2 font-medium text-ink">
            It does not delete your account on {account?.domain}. If you want that account gone, close it on the website yourself.
          </p>
        </>
      ),
      confirmLabel: "Delete from vault",
      destructive: true,
    });
    if (!ok) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteAccount(id);
      invalidate("accounts");
      invalidate(`account:${id}`);
      invalidate("jobs");
      toast.success("Deleted from your vault.");
      router.push("/accounts");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete this account. Nothing was removed.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Link href="/accounts" className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink">
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> Identity Vault
      </Link>

      <header className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h1 className="break-all font-mono text-lg font-semibold tracking-tight">{account.domain}</h1>
          <AccountStatusBadge status={account.status} />
        </div>
        <div className="flex flex-wrap items-center gap-1.5"><AccountTypeBadges account={account} /></div>
        <p className="text-sm text-muted">{expiry.label}</p>
        <p className="text-xs text-muted">Saved {formatDateTime(account.created_at)}</p>
      </header>

      {gone ? (
        <InlineMessage tone="info">This account was deleted from your vault. Its credentials and mailbox are gone.</InlineMessage>
      ) : (
        <>
          {account.status === "expired" && (
            <InlineMessage tone="warning">
              This temporary identity has expired. The password may no longer be needed, and new email can no longer arrive.
            </InlineMessage>
          )}

          <Panel title="Credentials" description="Reveal the password only when you need it.">
            <CredentialsPanel account={account} />
          </Panel>

          {account.status === "active" && (
            <Panel title="Chat with the agent" description="Ask about this account, check its mail, change saved details, or have the agent do something on the site.">
              <AccountChat accountId={account.id} domain={account.domain} />
            </Panel>
          )}

          <Panel
            title="Mailbox"
            description="Verification emails for this account."
            actions={
              <Link href={`/mailboxes?account=${account.id}`} className={buttonClass("ghost", "sm")}>
                <Mail className="h-4 w-4" aria-hidden="true" /> Open in Mailboxes
              </Link>
            }
          >
            <MailboxPanel accountId={account.id} />
          </Panel>
        </>
      )}

      {!gone && (
        <Panel title="Delete from vault">
          <p className="text-sm text-muted">
            Removes the stored credentials and mailbox from this app. Your account on <span className="font-mono">{account.domain}</span> is not deleted.
          </p>
          <Button className="mt-3" variant="danger" onClick={handleDelete} loading={deleting}>
            {!deleting && <Trash2 className="h-4 w-4" aria-hidden="true" />} Delete from vault
          </Button>
          {error && <div className="mt-3"><InlineMessage tone="danger">{error}</InlineMessage></div>}
        </Panel>
      )}
    </div>
  );
}
