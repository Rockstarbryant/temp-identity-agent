"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronRight, ExternalLink, Loader2, XCircle } from "lucide-react";
import { cancelRegistrationJob, getRegistrationJob } from "@/lib/api";
import { useCachedData } from "@/lib/useCachedData";
import { RESUMABLE_STATES, TERMINAL_STATES, canCancel, statusMeta, taskTypeLabel } from "@/lib/jobStatus";
import Timeline from "@/components/job/Timeline";
import QuestionCard from "@/components/QuestionCard";
import ManualKit from "@/components/ManualKit";
import CopyButton from "@/components/ui/CopyButton";
import Button, { buttonClass } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";

/**
 * A task shown inside the conversation, like a tool call in an AI client: a one-line header that
 * expands into the full step-by-step progress. Open while the agent works, closed once it is done.
 * The Activity page and the task page show the same task.
 */
export default function TaskBlock({ jobId, onFinished }: { jobId: string; onFinished?: () => void }) {
  const [finished, setFinished] = useState(false);
  const { data: job, error, refresh } = useCachedData(`job:${jobId}`, () => getRegistrationJob(jobId), {
    refreshMs: finished ? 0 : 3000,
  });
  const [open, setOpen] = useState<boolean | null>(null); // null: follow the default (open while running)
  const [cancelling, setCancelling] = useState(false);
  const reported = useRef(false);

  const state = job?.state ?? "queued";
  const done = TERMINAL_STATES.has(state);
  const paused = RESUMABLE_STATES.has(state);

  useEffect(() => {
    if (!job) return;
    if (done && !finished) setFinished(true);
    if ((done || paused) && !reported.current) {
      reported.current = true;
      onFinished?.();
    }
    if (!done && !paused) reported.current = false;
  }, [job, done, paused, finished, onFinished]);

  if (!job) {
    return (
      <div className="rounded-lg border border-line bg-surface px-3 py-2.5 text-sm text-muted">
        {error ? "Could not load this task." : <span className="inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading task…</span>}
      </div>
    );
  }

  const meta = statusMeta(job.state);
  const expanded = open ?? !done;
  const lastStep = job.steps[job.steps.length - 1];
  const taskUrl = typeof window !== "undefined" ? `${window.location.origin}/jobs/${job.id}` : `/jobs/${job.id}`;
  const failed = job.state === "failed" || job.state === "expired";

  async function handleCancel() {
    setCancelling(true);
    try {
      await cancelRegistrationJob(jobId);
      await refresh();
    } finally {
      setCancelling(false);
    }
  }

  const Icon = job.state === "completed" ? CheckCircle2 : failed || job.state === "cancelled" ? XCircle : paused ? AlertTriangle : Loader2;
  const tone = job.state === "completed" ? "text-success" : failed ? "text-danger" : paused ? "text-warning" : job.state === "cancelled" ? "text-muted" : "text-accent";

  return (
    <div className="w-full overflow-hidden rounded-lg border border-line bg-surface text-left">
      <button
        type="button" onClick={() => setOpen(!expanded)} aria-expanded={expanded}
        className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left hover:bg-subtle"
      >
        <Icon className={cn("h-4 w-4 shrink-0", tone, Icon === Loader2 && "animate-spin")} aria-hidden="true" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-ink">
            {taskTypeLabel(job)} <span className="font-mono text-xs font-normal text-muted">· {job.domain}</span>
          </span>
          <span className="block truncate text-xs text-muted">
            {!done && !paused && lastStep ? `${meta.label} · ${job.steps.length} step${job.steps.length === 1 ? "" : "s"}` : meta.label}
            {done && job.steps.length > 0 && ` · ${job.steps.length} step${job.steps.length === 1 ? "" : "s"}`}
          </span>
        </span>
        <ChevronRight className={cn("h-4 w-4 shrink-0 text-muted transition-transform", expanded && "rotate-90")} aria-hidden="true" />
      </button>

      {expanded && (
        <div className="space-y-3 border-t border-line px-3 py-3">
          {job.pending_question && job.state === "waiting_for_user" && (
            <QuestionCard key={job.pending_question.id} jobId={job.id} question={job.pending_question} onDone={() => void refresh()} />
          )}

          {paused && (
            <div className="rounded-md border border-warning-line bg-warning-soft p-3 text-sm">
              <p className="font-medium text-warning">{meta.label}</p>
              <p className="mt-1 text-ink">{job.error_message || meta.description}</p>
              <p className="mt-1 text-xs text-muted">The agent never solves CAPTCHAs. Solve it in the live browser, or sign up yourself with the details below.</p>
              <Link href={`/jobs/${job.id}`} className={cn(buttonClass("primary", "sm"), "mt-2")}>
                <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" /> Open the live browser
              </Link>
            </div>
          )}

          {job.manual_available && job.kind === "registration" && <ManualKit jobId={job.id} onSaved={() => void refresh()} />}

          <Timeline steps={job.steps} state={job.state} />

          <div className="flex flex-wrap items-center gap-1.5 border-t border-line pt-2.5">
            <Link href={`/jobs/${job.id}`} className={buttonClass("ghost", "sm")}>
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" /> Open task
            </Link>
            <CopyButton value={taskUrl} label="task link" textLabel="Copy link" withText className="!text-xs" />
            {canCancel(job.state) && (
              <Button variant="danger-ghost" size="sm" onClick={handleCancel} loading={cancelling}>Cancel task</Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
