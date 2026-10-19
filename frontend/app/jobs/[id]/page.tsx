"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  getRegistrationJob, resumeRegistrationJob, cancelRegistrationJob, retryRegistrationJob,
  deleteRegistrationJob, getAccount, revealCredentials,
  isAuthenticated, ApiError, RegistrationStep, RevealedCredentials,
} from "@/lib/api";
import { invalidate } from "@/lib/cache";
import { useCachedData } from "@/lib/useCachedData";
import StateBadge from "@/components/StateBadge";
import AiBadge from "@/components/AiBadge";
import LiveBrowser from "@/components/LiveBrowser";
import QuestionCard from "@/components/QuestionCard";
import ManualKit from "@/components/ManualKit";
import {
  CheckCircle2, XCircle, Loader2, AlertTriangle, ArrowRight, RotateCcw, Trash2,
  Copy, Check, Eye, KeyRound,
} from "lucide-react";

const TERMINAL = new Set(["completed", "failed", "cancelled", "expired"]);
const RESUMABLE = new Set(["captcha_required", "human_action_required"]);
const RETRYABLE = new Set(["failed", "cancelled", "expired"]);

// Fallback wording when a step has no detail (steps recorded before details existed).
const FALLBACK_LABELS: Record<string, string> = {
  "playbook.replay": "Used the steps saved from an earlier sign-up",
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
  "browser.read_text": "Read the text on the page",
  "profile.get": "Looked up your saved details",
  "user.ask": "Asked you for a detail",
  "site.report_auth_methods": "Checked how the site lets you sign in",
  "form.complete": "Submitted the form",
  "data.submit_result": "Saved the extracted information",
  "registration.get_status": "Checked job status",
  "registration.mark_complete": "Marked registration complete",
  "registration.mark_failed": "Registration could not be completed",
  "registration.mark_captcha_required": "Hit a CAPTCHA — needs you",
  "registration.mark_human_action_required": "Needs manual action from you",
};

const PAUSE_TITLES: Record<string, string> = {
  "registration.mark_captcha_required": "Hit a CAPTCHA",
  "registration.mark_human_action_required": "Needs manual action",
};

function stepText(step: RegistrationStep): string {
  const base = FALLBACK_LABELS[step.action] || step.action;
  if (!step.detail) return step.success ? base : `${base} (failed)`;
  const title = PAUSE_TITLES[step.action];
  return title ? `${title} — ${step.detail}` : step.detail;
}

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(value).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        });
      }}
      className="rounded-md p-1.5 text-black/40 hover:bg-black/5 hover:text-accent"
      aria-label={`Copy ${label}`}
    >
      {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
    </button>
  );
}

/** Shown when a job completes: the credentials right here, plus a link to the vault. */
function CredentialsCard({ accountId, domain }: { accountId: string; domain: string }) {
  const { data: account } = useCachedData(`account:${accountId}`, () => getAccount(accountId));
  const [revealed, setRevealed] = useState<RevealedCredentials | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reveal() {
    setBusy(true);
    setError(null);
    try {
      setRevealed(await revealCredentials(accountId));
    } catch {
      setError("Could not reveal the password. Open it from your vault instead.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-md border border-green-200 bg-green-50 p-4">
      <div className="flex items-center gap-2 font-medium text-green-800">
        <CheckCircle2 className="h-4 w-4" /> Your {domain} account is ready
      </div>
      {account ? (
        <dl className="mt-3 space-y-2 rounded-md bg-white p-3 text-sm">
          <div className="flex items-center justify-between gap-2">
            <dt className="text-black/50">Email</dt>
            <dd className="flex min-w-0 items-center gap-1 font-mono"><span className="truncate">{account.email}</span><CopyButton value={account.email} label="email" /></dd>
          </div>
          {account.username && (
            <div className="flex items-center justify-between gap-2">
              <dt className="text-black/50">Username</dt>
              <dd className="flex min-w-0 items-center gap-1 font-mono"><span className="truncate">{account.username}</span><CopyButton value={account.username} label="username" /></dd>
            </div>
          )}
          <div className="flex items-center justify-between gap-2">
            <dt className="text-black/50">Password</dt>
            {revealed ? (
              <dd className="flex min-w-0 items-center gap-1 font-mono"><span className="truncate">{revealed.password}</span><CopyButton value={revealed.password} label="password" /></dd>
            ) : (
              <dd>
                <button
                  onClick={reveal} disabled={busy}
                  className="flex items-center gap-1 rounded-md bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent/90 disabled:opacity-50"
                >
                  {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Eye className="h-3 w-3" />} Show password
                </button>
              </dd>
            )}
          </div>
        </dl>
      ) : (
        <div className="mt-3 flex items-center gap-2 text-sm text-green-700"><Loader2 className="h-4 w-4 animate-spin" /> Loading details…</div>
      )}
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      <Link href={`/accounts/${accountId}`} className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-green-800 underline">
        <KeyRound className="h-4 w-4" /> Open in your vault <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated()) router.push(`/login?next=/jobs/${id}`);
  }, [id, router]);

  // Keep polling until the job is finished. A paused job is still polled (more slowly):
  // pressing "continue" hands it back to the live browser, so its state changes on its own.
  const [finished, setFinished] = useState(false);
  const { data: job, refresh } = useCachedData(`job:${id}`, () => getRegistrationJob(id), {
    refreshMs: finished ? 0 : 3000,
  });
  useEffect(() => {
    setFinished(!!job && TERMINAL.has(job.state));
  }, [job]);

  async function run(action: () => Promise<void>, failMessage: string) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.message) : failMessage);
    } finally {
      setBusy(false);
    }
  }

  const handleResume = () =>
    run(async () => {
      await resumeRegistrationJob(id);
      await refresh();
    }, "Could not resume the job.");

  const handleCancel = () =>
    run(async () => {
      await cancelRegistrationJob(id);
      await refresh();
    }, "Could not cancel the job.");

  const handleRetry = () =>
    run(async () => {
      const fresh = await retryRegistrationJob(id);
      invalidate("jobs");
      router.push(`/jobs/${fresh.id}`);
    }, "Could not retry the job.");

  const handleDelete = () => {
    if (!confirm("Remove this job from your list? Any account it created stays in your vault.")) return;
    return run(async () => {
      await deleteRegistrationJob(id);
      invalidate("jobs");
      router.push("/dashboard");
    }, "Could not delete the job.");
  };

  if (!job) {
    return <div className="flex justify-center py-16 text-black/40"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  }

  const active = !TERMINAL.has(job.state) && !RESUMABLE.has(job.state);

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="truncate text-xl font-semibold">{job.domain}</h1>
            <p className="text-xs text-black/40">Started {job.started_at ? new Date(job.started_at).toLocaleString() : "—"}</p>
          </div>
          <StateBadge state={job.state} />
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <AiBadge provider={job.provider} model={job.model} />
          {job.kind === "account_setup" && <span className="rounded-full bg-black/5 px-2.5 py-1 text-xs text-black/60">Connect account</span>}
          {job.kind === "form" && <span className="rounded-full bg-black/5 px-2.5 py-1 text-xs text-black/60">Form</span>}
          {job.kind === "registration" && job.account_mode === "permanent" && (
            <span className="rounded-full bg-black/5 px-2.5 py-1 text-xs text-black/60">Permanent account</span>
          )}
          {job.source === "mcp" && <span className="rounded-full bg-black/5 px-2.5 py-1 text-xs text-black/60">From an AI client</span>}
        </div>
      </div>

      {job.pending_question && job.state === "waiting_for_user" && (
        <QuestionCard key={job.pending_question.id} jobId={id} question={job.pending_question} onDone={() => refresh()} />
      )}

      {job.state === "completed" && job.kind === "form" && job.result?.submitted && (
        <div className="space-y-3 rounded-md border border-green-200 bg-green-50 p-4">
          <div className="flex items-center gap-2 font-medium text-green-800">
            <CheckCircle2 className="h-4 w-4" /> Form submitted. This is what was sent:
          </div>
          <dl className="divide-y divide-green-200/70 rounded-md bg-white text-sm">
            {job.result.submitted.map((a, i) => (
              <div key={i} className="grid gap-0.5 px-3 py-2 sm:grid-cols-[40%_1fr] sm:gap-3">
                <dt className="text-black/50">{a.question}</dt>
                <dd className="break-words">{a.answer}</dd>
              </div>
            ))}
          </dl>
          {job.result.note && <p className="text-xs text-green-800">{job.result.note}</p>}
        </div>
      )}

      {job.state === "completed" && job.kind === "registration" && job.result?.summary && (
        <div className="space-y-2 rounded-md border border-black/10 bg-white p-4 text-sm">
          <p className="font-medium">Extracted information</p>
          <p className="text-black/70">{job.result.summary}</p>
          {job.result.data && Object.keys(job.result.data).length > 0 && (
            <pre className="overflow-x-auto rounded-md bg-black/[0.04] p-3 text-xs">{JSON.stringify(job.result.data, null, 2)}</pre>
          )}
        </div>
      )}

      {job.state === "completed" && job.kind === "account_setup" && (
        <div className="flex items-center justify-between gap-3 rounded-md border border-green-200 bg-green-50 p-4 text-sm text-green-800">
          <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 shrink-0" /> {job.result?.note || "Account connected."}</span>
          <Link href="/settings" className="shrink-0 font-medium underline">Back to settings</Link>
        </div>
      )}

      {job.state === "completed" && job.account_id && (
        <CredentialsCard accountId={job.account_id} domain={job.domain} />
      )}
      {job.state === "completed" && !job.account_id && job.kind !== "account_setup" && job.kind !== "form" && (
        <div className="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 p-4 text-sm text-green-700">
          <CheckCircle2 className="h-4 w-4" /> Account created —
          <Link href="/accounts" className="font-medium underline">view it in your vault</Link>
        </div>
      )}

      {RESUMABLE.has(job.state) && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-center gap-2 font-medium text-amber-800">
            <AlertTriangle className="h-4 w-4" /> Human action required
          </div>
          <p className="mt-1 text-sm text-amber-700">{job.error_message || "A manual step is needed on the target site."}</p>
          <p className="mt-2 text-xs text-amber-700/80">
            The agent&apos;s browser is waiting for you. Open the live browser below, complete the step
            (for example tick the CAPTCHA or pick the images), then press &ldquo;I&apos;m done — continue&rdquo;.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              onClick={handleResume} disabled={busy}
              className="flex items-center gap-1 rounded-md bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-60"
            >
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              I&apos;m done — continue <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {job.manual_available && job.kind === "registration" && (
        <ManualKit jobId={id} onSaved={() => refresh()} />
      )}

      {!TERMINAL.has(job.state) && (
        <LiveBrowser jobId={id} needsHuman={RESUMABLE.has(job.state)} finished={false} />
      )}

      {job.state === "failed" && job.error_message && (
        <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <XCircle className="mt-0.5 h-4 w-4 shrink-0" /> <span className="min-w-0 break-words">{job.error_message}</span>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {RETRYABLE.has(job.state) && (
          <button
            onClick={handleRetry} disabled={busy}
            className="flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-60"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />} Try again
          </button>
        )}
        {active && (
          <button onClick={handleCancel} disabled={busy} className="text-sm text-black/50 underline hover:text-red-600">
            Cancel this job
          </button>
        )}
        {!active && (
          <button
            onClick={handleDelete} disabled={busy}
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-black/50 hover:bg-red-50 hover:text-red-600 disabled:opacity-60"
          >
            <Trash2 className="h-4 w-4" /> Delete
          </button>
        )}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div>
        <h2 className="mb-2 text-sm font-medium text-black/60">Progress</h2>
        <ol className="space-y-2.5">
          {job.steps.map((step) => (
            <li key={step.step_index} className="flex items-start gap-2 text-sm">
              {step.success ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-600" />
              ) : (
                <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
              )}
              <span className="min-w-0 break-words">{stepText(step)}</span>
            </li>
          ))}
          {job.steps.length === 0 && <li className="text-sm text-black/40">Waiting for the agent to start…</li>}
        </ol>
      </div>
    </div>
  );
}
