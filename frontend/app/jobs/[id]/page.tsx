"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  getRegistrationJob, resumeRegistrationJob, cancelRegistrationJob,
  RegistrationJobDetail, isAuthenticated, ApiError,
} from "@/lib/api";
import StateBadge from "@/components/StateBadge";
import { CheckCircle2, XCircle, Loader2, AlertTriangle, ArrowRight } from "lucide-react";

const TERMINAL = new Set(["completed", "failed", "cancelled", "expired"]);
const RESUMABLE = new Set(["captcha_required", "human_action_required"]);

// Maps a raw tool name to the short, non-technical summary the spec
// requires ("concise action summaries only" — never raw agent reasoning).
function summarize(action: string, success: boolean): string {
  const labels: Record<string, string> = {
    "browser.open": "Opened the registration page",
    "browser.inspect": "Looked at the page",
    "browser.click": "Clicked a button",
    "browser.type": "Filled in a field",
    "browser.select": "Selected an option",
    "browser.scroll": "Scrolled the page",
    "browser.go_back": "Went back a page",
    "identity.create": "Created a temporary identity",
    "identity.get": "Checked identity details",
    "email.get_mailbox": "Checked the temporary mailbox",
    "email.list_messages": "Checked for new emails",
    "email.read_message": "Read a message",
    "email.wait_for_verification": "Waited for a verification email",
    "registration.get_status": "Checked job status",
    "registration.mark_complete": "Marked registration complete",
    "registration.mark_failed": "Registration could not be completed",
    "registration.mark_captcha_required": "Hit a CAPTCHA — needs you",
    "registration.mark_human_action_required": "Needs manual action from you",
  };
  const base = labels[action] || action;
  return success ? base : `${base} (failed)`;
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<RegistrationJobDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push(`/login?next=/jobs/${id}`);
      return;
    }

    async function poll() {
      try {
        const data = await getRegistrationJob(id);
        setJob(data);
        if (TERMINAL.has(data.state) && intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      } catch {
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    }

    poll();
    intervalRef.current = setInterval(poll, 3000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [id, router]);

  async function handleResume() {
    setBusy(true);
    setError(null);
    try {
      await resumeRegistrationJob(id);
      if (!intervalRef.current) intervalRef.current = setInterval(async () => setJob(await getRegistrationJob(id)), 3000);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.message) : "Could not resume the job.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancel() {
    setBusy(true);
    try {
      await cancelRegistrationJob(id);
      setJob(await getRegistrationJob(id));
    } catch (err) {
      setError(err instanceof ApiError ? String(err.message) : "Could not cancel the job.");
    } finally {
      setBusy(false);
    }
  }

  if (!job) {
    return <div className="flex justify-center py-16 text-black/40"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{job.domain}</h1>
          <p className="text-xs text-black/40">Started {job.started_at ? new Date(job.started_at).toLocaleString() : "—"}</p>
        </div>
        <StateBadge state={job.state} />
      </div>

      {RESUMABLE.has(job.state) && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-center gap-2 font-medium text-amber-800">
            <AlertTriangle className="h-4 w-4" /> Human action required
          </div>
          <p className="mt-1 text-sm text-amber-700">{job.error_message || "Please complete the required step on the target site, then resume."}</p>
          <button
            onClick={handleResume} disabled={busy}
            className="mt-3 flex items-center gap-1 rounded-md bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-60"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            I&apos;ve completed it — Resume <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      )}

      {job.state === "failed" && job.error_message && (
        <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <XCircle className="h-4 w-4 shrink-0 mt-0.5" /> {job.error_message}
        </div>
      )}

      {job.state === "completed" && (
        <div className="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 p-4 text-sm text-green-700">
          <CheckCircle2 className="h-4 w-4" /> Account created —
          <Link href="/accounts" className="font-medium underline">view it in your vault</Link>
        </div>
      )}

      {!TERMINAL.has(job.state) && !RESUMABLE.has(job.state) && (
        <button
          onClick={handleCancel} disabled={busy}
          className="text-sm text-black/50 underline hover:text-red-600"
        >
          Cancel this job
        </button>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div>
        <h2 className="mb-2 text-sm font-medium text-black/60">Progress</h2>
        <ol className="space-y-2">
          {job.steps.map((step) => (
            <li key={step.step_index} className="flex items-center gap-2 text-sm">
              {step.tool_result?.success ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600" />
              ) : (
                <XCircle className="h-4 w-4 shrink-0 text-red-500" />
              )}
              {summarize(step.action, step.tool_result?.success ?? false)}
            </li>
          ))}
          {job.steps.length === 0 && <li className="text-sm text-black/40">Waiting for the agent to start…</li>}
        </ol>
      </div>
    </div>
  );
}
