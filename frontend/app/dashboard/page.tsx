"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Activity, Plus, RotateCcw, Trash2 } from "lucide-react";
import {
  ApiError, RegistrationJob, clearFinishedJobs, deleteRegistrationJob, listRegistrationJobs, retryRegistrationJob,
} from "@/lib/api";
import { invalidate } from "@/lib/cache";
import { useCachedData } from "@/lib/useCachedData";
import { useRequireAuth } from "@/lib/useRequireAuth";
import {
  JOB_FILTERS, JobFilter, POLLING_STATES, canDismiss, canRetry, matchesFilter, taskTypeLabel,
} from "@/lib/jobStatus";
import { formatDateTime, timeAgo } from "@/lib/format";
import StateBadge from "@/components/StateBadge";
import AiBadge from "@/components/AiBadge";
import Button, { buttonClass } from "@/components/ui/Button";
import PageHeader from "@/components/ui/PageHeader";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/States";
import { useConfirm, useToast } from "@/components/ui/Feedback";
import { cn } from "@/components/ui/cn";

export default function ActivityPage() {
  const router = useRouter();
  const ready = useRequireAuth();
  const confirm = useConfirm();
  const toast = useToast();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);
  const [filter, setFilter] = useState<JobFilter>("all");

  // Polling only runs while at least one job can still change. The first fetch (or cached data) decides.
  const [hasActive, setHasActive] = useState(true);
  const { data, error, loading, refresh, mutate } = useCachedData(
    ready ? "jobs" : null,
    async () => {
      const results = (await listRegistrationJobs()).results;
      setHasActive(results.some((j) => POLLING_STATES.has(j.state)));
      return results;
    },
    { refreshMs: hasActive ? 4000 : 0 },
  );

  const jobs: RegistrationJob[] = useMemo(() => data ?? [], [data]);
  const visible = useMemo(() => jobs.filter((j) => matchesFilter(j.state, filter)), [jobs, filter]);
  const counts = useMemo(
    () => Object.fromEntries(JOB_FILTERS.map((f) => [f.id, jobs.filter((j) => matchesFilter(j.state, f.id)).length])) as Record<JobFilter, number>,
    [jobs],
  );
  const clearable = jobs.filter((j) => canRetry(j.state)).length;

  async function handleRetry(job: RegistrationJob) {
    const ok = await confirm({
      title: `Start a new attempt for ${job.domain}?`,
      description:
        "This creates a new task for the same site. The earlier attempt may already have sent something to the website before it stopped, so check your Mailboxes and Identity Vault first if you are unsure.",
      confirmLabel: "Start new attempt",
    });
    if (!ok) return;
    setBusyId(job.id);
    try {
      const fresh = await retryRegistrationJob(job.id);
      invalidate("jobs");
      setHasActive(true);
      router.push(`/jobs/${fresh.id}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not retry the task.");
      setBusyId(null);
    }
  }

  async function handleDismiss(job: RegistrationJob) {
    const ok = await confirm({
      title: `Remove ${job.domain} from Activity?`,
      description: "This only hides the task from this list. Any account it created stays in your Identity Vault, and nothing is deleted from the website.",
      confirmLabel: "Remove from list",
      destructive: true,
    });
    if (!ok) return;
    setBusyId(job.id);
    try {
      await deleteRegistrationJob(job.id);
      mutate((prev) => (prev ?? []).filter((j) => j.id !== job.id));
      toast.success("Task removed from Activity.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove the task.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleClear() {
    const ok = await confirm({
      title: `Clear ${clearable} finished task${clearable === 1 ? "" : "s"}?`,
      description: "Failed, cancelled and expired tasks are hidden from this list. Completed tasks are kept, and no accounts are deleted.",
      confirmLabel: "Clear list",
      destructive: true,
    });
    if (!ok) return;
    setClearing(true);
    try {
      await clearFinishedJobs();
      mutate((prev) => (prev ?? []).filter((j) => !canRetry(j.state)));
      toast.success("Cleared.");
    } catch {
      toast.error("Could not clear the list.");
    } finally {
      setClearing(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Activity"
        description="Every task you have started, with its current state."
        actions={
          <>
            {clearable > 0 && (
              <Button variant="ghost" onClick={handleClear} loading={clearing}>
                {!clearing && <Trash2 className="h-4 w-4" aria-hidden="true" />} Clear finished ({clearable})
              </Button>
            )}
            <Link href="/new" className={buttonClass("primary")}>
              <Plus className="h-4 w-4" aria-hidden="true" /> New task
            </Link>
          </>
        }
      />

      {jobs.length > 0 && (
        <div role="group" aria-label="Filter tasks by state" className="-mx-4 mb-4 flex gap-2 overflow-x-auto px-4 pb-1 md:mx-0 md:px-0">
          {JOB_FILTERS.map((f) => {
            const active = filter === f.id;
            return (
              <button
                key={f.id}
                type="button"
                aria-pressed={active}
                onClick={() => setFilter(f.id)}
                className={cn(
                  "shrink-0 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
                  active ? "border-accent bg-accent-soft text-accent-strong" : "border-line-strong bg-surface text-muted hover:bg-subtle hover:text-ink",
                )}
              >
                {f.label} <span className="tabular opacity-70">{counts[f.id]}</span>
              </button>
            );
          })}
        </div>
      )}

      {!ready || (loading && !error) ? (
        <ListSkeleton />
      ) : error && data === undefined ? (
        <ErrorState title="Could not load your tasks" message="Check your connection and try again." onRetry={() => void refresh()} />
      ) : jobs.length === 0 ? (
        <EmptyState
          icon={<Activity className="h-4 w-4" aria-hidden="true" />}
          title="No tasks yet"
          description="Start one from Home and its progress will show up here."
          action={<Link href="/new" className={buttonClass("primary")}>Start a task</Link>}
        />
      ) : visible.length === 0 ? (
        <EmptyState title="Nothing matches this filter" action={<Button onClick={() => setFilter("all")}>Show all tasks</Button>} />
      ) : (
        <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
          {visible.map((job) => {
            const busy = busyId === job.id;
            return (
              <li key={job.id} className="flex items-stretch">
                <Link href={`/jobs/${job.id}`} className="min-w-0 flex-1 px-4 py-3.5 hover:bg-subtle">
                  <span className="flex items-start justify-between gap-3">
                    <span className="min-w-0">
                      <span className="block truncate font-mono text-sm font-medium">{job.domain}</span>
                      <span className="mt-0.5 block text-xs text-muted">
                        {taskTypeLabel(job)}
                        <span aria-hidden="true"> · </span>
                        <time dateTime={job.created_at} title={formatDateTime(job.created_at)}>{timeAgo(job.created_at)}</time>
                      </span>
                    </span>
                    <StateBadge state={job.state} />
                  </span>
                  <span className="mt-2 flex min-w-0 flex-wrap items-center gap-2">
                    <AiBadge provider={job.provider} model={job.model} />
                    {job.account_id && <span className="text-xs text-success">Account saved to your vault</span>}
                  </span>
                </Link>
                {(canRetry(job.state) || canDismiss(job.state)) && (
                  <div className="flex shrink-0 flex-col justify-center gap-1 border-l border-line px-1.5">
                    {canRetry(job.state) && (
                      <Button
                        variant="ghost" size="sm" loading={busy} onClick={() => handleRetry(job)}
                        aria-label={`Retry ${job.domain}`} title="Retry" className="!px-2"
                      >
                        {!busy && <RotateCcw className="h-4 w-4" aria-hidden="true" />}
                      </Button>
                    )}
                    {canDismiss(job.state) && (
                      <Button
                        variant="danger-ghost" size="sm" disabled={busy} onClick={() => handleDismiss(job)}
                        aria-label={`Remove ${job.domain} from Activity`} title="Remove from list" className="!px-2"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </Button>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {jobs.length >= 20 && <p className="mt-3 text-xs text-muted">Showing your 20 most recent tasks.</p>}
    </div>
  );
}
