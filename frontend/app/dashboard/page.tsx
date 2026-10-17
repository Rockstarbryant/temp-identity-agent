"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  listRegistrationJobs, retryRegistrationJob, deleteRegistrationJob, clearFinishedJobs,
  isAuthenticated, ApiError, RegistrationJob,
} from "@/lib/api";
import { invalidate } from "@/lib/cache";
import { useCachedData } from "@/lib/useCachedData";
import StateBadge from "@/components/StateBadge";
import AiBadge from "@/components/AiBadge";
import { Plus, Loader2, RotateCcw, Trash2 } from "lucide-react";

const RETRYABLE = new Set(["failed", "cancelled", "expired"]);

// States that still need live updates (including paused ones waiting for the user).
const ACTIVE = new Set([
  "queued", "starting", "opening_site", "analyzing", "identity_created",
  "filling_form", "submitting", "waiting_for_email", "verifying",
  "captcha_required", "human_action_required",
]);

export default function DashboardPage() {
  const router = useRouter();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated()) router.push("/login?next=/dashboard");
  }, [router]);

  // First fetch (or cached data) decides whether we keep polling.
  // Once every job is terminal, refreshMs becomes 0 and polling stops.
  const [hasActiveJobs, setHasActiveJobs] = useState(true);

  const { data, loading, mutate } = useCachedData(
    "jobs",
    async () => {
      const results = (await listRegistrationJobs()).results;
      setHasActiveJobs(results.some((j) => ACTIVE.has(j.state)));
      return results;
    },
    { refreshMs: hasActiveJobs ? 4000 : 0 }
  );

  const jobs: RegistrationJob[] = data ?? [];
  const finishedCount = jobs.filter((j) => RETRYABLE.has(j.state)).length;

  async function handleRetry(job: RegistrationJob) {
    setBusyId(job.id);
    setError(null);
    try {
      const fresh = await retryRegistrationJob(job.id);
      invalidate("jobs");
      // A new active job just appeared → re-enable polling
      setHasActiveJobs(true);
      router.push(`/jobs/${fresh.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not retry the job.");
      setBusyId(null);
    }
  }

  async function handleDelete(job: RegistrationJob) {
    if (!confirm(`Remove this ${job.domain} job from your list? Any account it created stays in your vault.`)) return;
    setBusyId(job.id);
    setError(null);
    try {
      await deleteRegistrationJob(job.id);
      mutate((prev) => {
        const next = (prev ?? []).filter((j) => j.id !== job.id);
        setHasActiveJobs(next.some((j) => ACTIVE.has(j.state)));
        return next;
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete the job.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleClear() {
    if (!confirm(`Remove ${finishedCount} failed/cancelled job(s) from your list? Completed jobs are kept.`)) return;
    setClearing(true);
    setError(null);
    try {
      await clearFinishedJobs();
      mutate((prev) => {
        const next = (prev ?? []).filter((j) => !RETRYABLE.has(j.state));
        setHasActiveJobs(next.some((j) => ACTIVE.has(j.state)));
        return next;
      });
    } catch {
      setError("Could not clear the list.");
    } finally {
      setClearing(false);
    }
  }

  return (
    <div>
      <div className="mb-5 flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Your jobs</h1>
        <div className="flex items-center gap-2">
          {finishedCount > 0 && (
            <button
              onClick={handleClear} disabled={clearing}
              className="flex items-center gap-1 rounded-md px-2.5 py-1.5 text-sm text-black/60 hover:bg-black/5 hover:text-red-600 disabled:opacity-50"
            >
              {clearing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
              Clear failed ({finishedCount})
            </button>
          )}
          <Link href="/" className="flex items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-sm text-white hover:bg-accent/90">
            <Plus className="h-4 w-4" /> New
          </Link>
        </div>
      </div>

      {error && <p className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {loading ? (
        <div className="flex justify-center py-12 text-black/40"><Loader2 className="h-5 w-5 animate-spin" /></div>
      ) : jobs.length === 0 ? (
        <p className="py-12 text-center text-sm text-black/50">
          No jobs yet. <Link href="/" className="text-accent hover:underline">Create one</Link> to get started.
        </p>
      ) : (
        <ul className="divide-y divide-black/10 rounded-md border border-black/10 bg-white">
          {jobs.map((job) => {
            const busy = busyId === job.id;
            return (
              <li key={job.id} className="flex items-stretch">
                <Link href={`/jobs/${job.id}`} className="min-w-0 flex-1 px-4 py-3 hover:bg-black/[0.02]">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{job.domain}</p>
                      <p className="text-xs text-black/40">{new Date(job.created_at).toLocaleString()}</p>
                    </div>
                    <StateBadge state={job.state} />
                  </div>
                  <div className="mt-1.5 flex min-w-0"><AiBadge provider={job.provider} model={job.model} /></div>
                </Link>
                {(RETRYABLE.has(job.state) || !ACTIVE.has(job.state)) && (
                  <div className="flex shrink-0 flex-col justify-center gap-1 border-l border-black/5 px-1.5">
                    {RETRYABLE.has(job.state) && (
                      <button
                        onClick={() => handleRetry(job)} disabled={busy} aria-label={`Retry ${job.domain}`} title="Retry"
                        className="rounded-md p-2 text-black/40 hover:bg-accent/10 hover:text-accent disabled:opacity-50"
                      >
                        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                      </button>
                    )}
                    {!ACTIVE.has(job.state) && (
                      <button
                        onClick={() => handleDelete(job)} disabled={busy} aria-label={`Delete ${job.domain}`} title="Delete"
                        className="rounded-md p-2 text-black/40 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}