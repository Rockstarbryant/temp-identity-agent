"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2, ExternalLink, KeyRound, RotateCcw, Trash2, XCircle,
} from "lucide-react";
import {
  ApiError, deleteRegistrationJob, cancelRegistrationJob, getAccount, getRegistrationJob, resumeRegistrationJob,
  retryRegistrationJob,
} from "@/lib/api";
import { invalidate } from "@/lib/cache";
import { useCachedData } from "@/lib/useCachedData";
import { useRequireAuth } from "@/lib/useRequireAuth";
import {
  RESUMABLE_STATES, TERMINAL_STATES, canCancel, canDismiss, canRetry, friendlyJobError, mayHaveSubmitted,
  statusMeta, taskTypeLabel,
} from "@/lib/jobStatus";
import { formatDateTime, isSafeHttpUrl } from "@/lib/format";
import StateBadge from "@/components/StateBadge";
import AiBadge from "@/components/AiBadge";
import LiveBrowser from "@/components/LiveBrowser";
import QuestionCard from "@/components/QuestionCard";
import ManualKit from "@/components/ManualKit";
import Timeline from "@/components/job/Timeline";
import CredentialsPanel from "@/components/vault/CredentialsPanel";
import Badge from "@/components/ui/Badge";
import Button, { buttonClass } from "@/components/ui/Button";
import { Panel } from "@/components/ui/Card";
import { EmptyState, ErrorState, InlineMessage, PageSpinner } from "@/components/ui/States";
import { useConfirm, useToast } from "@/components/ui/Feedback";

/** The finished account: credentials right here, with the vault as the permanent home. */
function CredentialsCard({ accountId, domain }: { accountId: string; domain: string }) {
  const { data: account, error } = useCachedData(`account:${accountId}`, () => getAccount(accountId));
  return (
    <section className="space-y-3 rounded-lg border border-success-line bg-success-soft p-4">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-success">
        <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> Your <span className="font-mono">{domain}</span> account is ready
      </h2>
      {account ? (
        <CredentialsPanel account={account} />
      ) : error ? (
        <InlineMessage tone="warning">Could not load the account details here. Open it from your Identity Vault instead.</InlineMessage>
      ) : (
        <p role="status" className="text-sm text-muted">Loading account details</p>
      )}
      <Link href={`/accounts/${accountId}`} className="inline-flex items-center gap-1 text-sm font-medium text-success underline">
        <KeyRound className="h-4 w-4" aria-hidden="true" /> Open in Identity Vault <ArrowRight className="h-4 w-4" aria-hidden="true" />
      </Link>
    </section>
  );
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const ready = useRequireAuth();
  const confirm = useConfirm();
  const toast = useToast();
  const [busy, setBusy] = useState<"resume" | "cancel" | "retry" | "delete" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [browserWaiting, setBrowserWaiting] = useState(false);

  // Poll until the job is finished. A paused job is still polled: pressing Continue hands it back
  // to the agent, so its state changes on its own.
  const [finished, setFinished] = useState(false);
  const { data: job, error: loadError, refresh } = useCachedData(
    ready ? `job:${id}` : null,
    () => getRegistrationJob(id),
    { refreshMs: finished ? 0 : 3000 },
  );
  useEffect(() => {
    setFinished(!!job && TERMINAL_STATES.has(job.state));
  }, [job]);

  async function run(kind: NonNullable<typeof busy>, action: () => Promise<void>, failMessage: string) {
    setBusy(kind);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.message) : failMessage);
    } finally {
      setBusy(null);
    }
  }

  if (!ready) return <PageSpinner />;
  if (!job) {
    if (loadError instanceof ApiError && loadError.status === 404) {
      return (
        <EmptyState
          title="Task not found"
          description="It may have been removed from Activity."
          action={<Link href="/dashboard" className={buttonClass("primary")}>Back to Activity</Link>}
        />
      );
    }
    if (loadError) return <ErrorState title="Could not load this task" message="Check your connection and try again." onRetry={() => void refresh()} />;
    return <PageSpinner label="Loading task" />;
  }

  const meta = statusMeta(job.state);
  const paused = RESUMABLE_STATES.has(job.state);
  const errorText = friendlyJobError(job);

  const retryCaution =
    canRetry(job.state) &&
    (job.kind === "form"
      ? mayHaveSubmitted(job.steps)
        ? "The form may already have been submitted before this task stopped. Submitting it again could create a duplicate response."
        : null
      : job.kind === "registration" && job.identity_id
        ? "The agent had already started signing up before this task stopped, so the site may have received a registration. A new attempt creates a new identity and a new submission."
        : null);

  async function handleResume() {
    await run("resume", async () => {
      await resumeRegistrationJob(id);
      await refresh();
    }, "Could not continue the task.");
  }

  async function handleCancel() {
    const ok = await confirm({
      title: "Cancel this task?",
      description: "The agent stops where it is. Anything it already sent to the website is not undone.",
      confirmLabel: "Cancel task",
      cancelLabel: "Keep running",
      destructive: true,
    });
    if (!ok) return;
    await run("cancel", async () => {
      await cancelRegistrationJob(id);
      invalidate("jobs");
      await refresh();
    }, "Could not cancel the task.");
  }

  async function handleRetry() {
    const ok = await confirm({
      title: "Start a new attempt?",
      description: retryCaution ?? "This creates a new task for the same site. This one stays in Activity as a record.",
      confirmLabel: "Start new attempt",
    });
    if (!ok) return;
    await run("retry", async () => {
      const fresh = await retryRegistrationJob(id);
      invalidate("jobs");
      router.push(`/jobs/${fresh.id}`);
    }, "Could not start a new attempt.");
  }

  async function handleDelete() {
    const ok = await confirm({
      title: "Remove this task from Activity?",
      description: "This only hides the task. Any account it created stays in your Identity Vault, and nothing is deleted from the website.",
      confirmLabel: "Remove from list",
      destructive: true,
    });
    if (!ok) return;
    await run("delete", async () => {
      await deleteRegistrationJob(id);
      invalidate("jobs");
      toast.success("Task removed from Activity.");
      router.push("/dashboard");
    }, "Could not remove the task.");
  }

  const targetUrl = job.target_url && isSafeHttpUrl(job.target_url) ? job.target_url : "";

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Link href="/dashboard" className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink">
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> Activity
      </Link>

      {/* Summary */}
      <header className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="break-all font-mono text-lg font-semibold tracking-tight">{job.domain}</h1>
            {targetUrl && (
              <a
                href={targetUrl} target="_blank" rel="noopener noreferrer"
                className="mt-0.5 inline-flex max-w-full items-center gap-1 text-xs text-muted hover:text-ink"
              >
                <span className="truncate font-mono">{targetUrl}</span>
                <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
                <span className="sr-only">(opens in a new tab)</span>
              </a>
            )}
          </div>
          <StateBadge state={job.state} />
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <Badge>{taskTypeLabel(job)}</Badge>
          {job.source === "mcp" && <Badge>Started by an AI client</Badge>}
          <AiBadge provider={job.provider} model={job.model} />
        </div>
        <p className="text-sm text-muted">{meta.description}</p>
        <p className="text-xs text-muted">
          {job.started_at ? `Started ${formatDateTime(job.started_at)}` : `Created ${formatDateTime(job.created_at)}`}
          {job.completed_at && ` · Finished ${formatDateTime(job.completed_at)}`}
        </p>
        <span className="sr-only" role="status" aria-live="polite">Task status: {meta.label}</span>
      </header>

      {/* Needs the user */}
      {job.pending_question && job.state === "waiting_for_user" && (
        <QuestionCard key={job.pending_question.id} jobId={id} question={job.pending_question} onDone={() => void refresh()} />
      )}

      {paused && (
        <section className="rounded-lg border border-warning-line bg-warning-soft p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-warning">
            <AlertTriangle className="h-4 w-4" aria-hidden="true" /> {meta.label}
          </h2>
          <p className="mt-1 text-sm text-ink">{job.error_message || meta.description}</p>
          <p className="mt-2 text-sm text-muted">
            {browserWaiting
              ? "The agent's browser is waiting for you. Open the browser preview below, complete the step on the page, then press Continue."
              : "Open the browser preview below to see where the agent stopped. If the browser is no longer waiting, Continue starts a new browser session and revisits the page, so progress on the site may not carry over."}
          </p>
          <p className="mt-2 text-xs text-muted">The agent never solves or bypasses CAPTCHAs and other security checks. They are always left to you.</p>
          <div className="mt-3">
            <Button variant="primary" onClick={handleResume} loading={busy === "resume"}>
              Continue <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
        </section>
      )}

      {job.manual_available && job.kind === "registration" && <ManualKit jobId={id} onSaved={() => void refresh()} />}

      {/* Browser */}
      {!TERMINAL_STATES.has(job.state) && (
        <LiveBrowser jobId={id} needsHuman={paused} finished={false} onInteractiveChange={setBrowserWaiting} />
      )}

      {/* Results */}
      {job.state === "completed" && job.kind === "form" && job.result?.submitted && (
        <section className="space-y-3 rounded-lg border border-success-line bg-success-soft p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-success">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> Form submitted. This is what was sent:
          </h2>
          <dl className="divide-y divide-line rounded-md border border-line bg-surface text-sm">
            {job.result.submitted.map((a, i) => (
              <div key={i} className="grid gap-0.5 px-3 py-2 sm:grid-cols-[40%_1fr] sm:gap-3">
                <dt className="text-muted">{a.question}</dt>
                <dd className="break-words">{a.answer}</dd>
              </div>
            ))}
          </dl>
          {job.result.note && <p className="text-xs text-muted">{job.result.note}</p>}
        </section>
      )}

      {job.state === "completed" && (job.kind === "registration" || job.kind === "account_task") && job.result?.summary && (
        <Panel title="Information the agent found">
          <p className="text-sm">{job.result.summary}</p>
          {job.result.data && Object.keys(job.result.data).length > 0 && (
            <pre className="mt-3 overflow-x-auto rounded-md bg-subtle p-3 font-mono text-xs">{JSON.stringify(job.result.data, null, 2)}</pre>
          )}
        </Panel>
      )}

      {job.state === "completed" && job.kind === "account_setup" && (
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-success-line bg-success-soft p-4 text-sm">
          <span className="flex items-center gap-2 text-success">
            <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" /> {job.result?.note || "Account connected."}
          </span>
          <Link href="/settings?tab=accounts" className="font-medium text-success underline">Back to Settings</Link>
        </section>
      )}

      {job.state === "completed" && job.account_id && <CredentialsCard accountId={job.account_id} domain={job.domain} />}
      {job.state === "completed" && !job.account_id && job.kind === "registration" && (
        <InlineMessage tone="success">
          Completed. Check your <Link href="/accounts" className="font-medium underline">Identity Vault</Link> for the account.
        </InlineMessage>
      )}

      {/* Failure */}
      {(job.state === "failed" || job.state === "expired") && errorText && (
        <section role="alert" className="flex items-start gap-2 rounded-lg border border-danger-line bg-danger-soft p-4 text-sm">
          <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden="true" />
          <div className="min-w-0">
            <p className="font-medium text-danger">{job.state === "expired" ? "This task ran out of time" : "This task did not finish"}</p>
            <p className="mt-0.5 break-words text-ink">{errorText}</p>
            {job.error_code && (
              <details className="mt-2 text-xs text-muted">
                <summary className="cursor-pointer select-none hover:text-ink">Technical details</summary>
                <p className="mt-1 break-all font-mono">{job.error_code}</p>
              </details>
            )}
          </div>
        </section>
      )}
      {retryCaution && <InlineMessage tone="warning">{retryCaution}</InlineMessage>}

      {/* Controls */}
      {(canRetry(job.state) || canCancel(job.state) || canDismiss(job.state)) && (
        <div className="flex flex-wrap items-center gap-2">
          {canRetry(job.state) && (
            <Button variant="primary" onClick={handleRetry} loading={busy === "retry"}>
              {busy !== "retry" && <RotateCcw className="h-4 w-4" aria-hidden="true" />} Try again
            </Button>
          )}
          {canCancel(job.state) && (
            <Button variant="danger-ghost" onClick={handleCancel} loading={busy === "cancel"}>Cancel task</Button>
          )}
          {canDismiss(job.state) && (
            <Button variant="danger-ghost" onClick={handleDelete} loading={busy === "delete"}>
              {busy !== "delete" && <Trash2 className="h-4 w-4" aria-hidden="true" />} Remove from Activity
            </Button>
          )}
        </div>
      )}
      {error && <InlineMessage tone="danger">{error}</InlineMessage>}

      {/* Timeline */}
      <Panel title="Timeline" description="What the agent did, in order.">
        <Timeline steps={job.steps} state={job.state} />
      </Panel>
    </div>
  );
}
