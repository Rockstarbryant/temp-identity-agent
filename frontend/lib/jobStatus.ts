import type { RegistrationJob, RegistrationStep } from "@/lib/api";

/**
 * Single source of truth for how backend job states are named, grouped and described.
 * The state values mirror RegistrationJob.State in the Django backend. An unrecognised
 * state is shown as "Unknown status" and is never treated as success.
 */

export type StatusGroup =
  | "running"
  | "waiting_user"
  | "waiting_email"
  | "completed"
  | "failed"
  | "cancelled"
  | "expired"
  | "unknown";

export type Tone = "neutral" | "info" | "success" | "warning" | "danger" | "accent";

export interface StatusMeta {
  label: string;
  group: StatusGroup;
  tone: Tone;
  /** One sentence for the job page: what is happening and what the user can do. */
  description: string;
}

const META: Record<string, StatusMeta> = {
  queued: { label: "Queued", group: "running", tone: "info", description: "The task is waiting for a worker to pick it up." },
  starting: { label: "Starting", group: "running", tone: "info", description: "The agent is getting ready." },
  opening_site: { label: "Opening site", group: "running", tone: "info", description: "The agent is opening the website in a browser." },
  analyzing: { label: "Reading the page", group: "running", tone: "info", description: "The agent is looking at the page to decide what to do." },
  identity_created: { label: "Identity ready", group: "running", tone: "info", description: "An identity has been prepared for this task." },
  filling_form: { label: "Filling in the form", group: "running", tone: "info", description: "The agent is entering details into the form." },
  submitting: { label: "Submitting", group: "running", tone: "info", description: "The agent is submitting the form." },
  verifying: { label: "Verifying", group: "running", tone: "info", description: "The agent is completing the verification step." },
  waiting_for_email: { label: "Waiting for email", group: "waiting_email", tone: "warning", description: "The agent is waiting for a verification email to arrive." },
  waiting_for_user: { label: "Needs your answer", group: "waiting_user", tone: "warning", description: "The agent is waiting for a detail only you can provide." },
  captcha_required: { label: "CAPTCHA needs you", group: "waiting_user", tone: "warning", description: "The site is showing a CAPTCHA. The agent does not bypass these, so a person has to complete it." },
  human_action_required: { label: "Action needed", group: "waiting_user", tone: "warning", description: "The site needs a step the agent is not allowed to do for you." },
  completed: { label: "Completed", group: "completed", tone: "success", description: "The task finished." },
  failed: { label: "Failed", group: "failed", tone: "danger", description: "The task could not be completed." },
  cancelled: { label: "Cancelled", group: "cancelled", tone: "neutral", description: "This task was cancelled." },
  expired: { label: "Expired", group: "expired", tone: "neutral", description: "This task timed out before it finished." },
};

export function humanizeState(state: string): string {
  const s = state.replace(/_/g, " ").trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "Unknown";
}

export function statusMeta(state: string): StatusMeta {
  return (
    META[state] ?? {
      label: "Unknown status",
      group: "unknown",
      tone: "neutral",
      description: `The server reported a status this page does not recognise (${humanizeState(state)}).`,
    }
  );
}

export const RESUMABLE_STATES = new Set(["captcha_required", "human_action_required"]);
export const TERMINAL_STATES = new Set(["completed", "failed", "cancelled", "expired"]);
export const RETRYABLE_STATES = new Set(["failed", "cancelled", "expired"]);

/** States that still change on their own (or are paused awaiting the user), so polling is worthwhile. */
export const POLLING_STATES = new Set([
  "queued", "starting", "opening_site", "analyzing", "identity_created", "filling_form",
  "submitting", "waiting_for_email", "verifying", "waiting_for_user", "captcha_required", "human_action_required",
]);

/** Backend rule: only jobs that are neither running nor paused-for-user can be dismissed. */
export function canDismiss(state: string): boolean {
  return TERMINAL_STATES.has(state);
}
export function canRetry(state: string): boolean {
  return RETRYABLE_STATES.has(state);
}
/** The backend accepts cancellation of any non-terminal job, including paused ones. */
export function canCancel(state: string): boolean {
  return state in META && !TERMINAL_STATES.has(state);
}

// --- Activity filters ---------------------------------------------------------------

export type JobFilter = "all" | "running" | "needs_you" | "waiting_email" | "completed" | "ended";

export const JOB_FILTERS: { id: JobFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "running", label: "Running" },
  { id: "needs_you", label: "Needs you" },
  { id: "waiting_email", label: "Waiting for email" },
  { id: "completed", label: "Completed" },
  { id: "ended", label: "Failed or ended" },
];

export function matchesFilter(state: string, filter: JobFilter): boolean {
  const g = statusMeta(state).group;
  switch (filter) {
    case "all": return true;
    case "running": return g === "running";
    case "needs_you": return g === "waiting_user";
    case "waiting_email": return g === "waiting_email";
    case "completed": return g === "completed";
    case "ended": return g === "failed" || g === "cancelled" || g === "expired";
  }
}

// --- Task kinds -----------------------------------------------------------------------

export function taskTypeLabel(job: Pick<RegistrationJob, "kind" | "account_mode">): string {
  if (job.kind === "form") return "Form fill";
  if (job.kind === "account_setup") return "Connect sign-in account";
  if (job.kind === "account_task") return "Task on your account";
  return job.account_mode === "permanent" ? "Registration, permanent identity" : "Registration, temporary identity";
}

// --- Execution timeline ---------------------------------------------------------------

/** Wording for steps that carry no secret-free `detail` (for example steps recorded before details existed). */
const STEP_LABELS: Record<string, string> = {
  "playbook.replay": "Reused steps saved from an earlier sign-up",
  "browser.open": "Opened the page",
  "browser.inspect": "Looked at the page",
  "browser.click": "Clicked a button",
  "browser.type": "Filled in a field",
  "browser.select": "Selected an option",
  "browser.scroll": "Scrolled the page",
  "browser.go_back": "Went back a page",
  "browser.read_text": "Read the text on the page",
  "identity.create": "Prepared an identity",
  "identity.get": "Checked identity details",
  "email.get_mailbox": "Checked the mailbox",
  "email.list_messages": "Checked for new emails",
  "email.read_message": "Read an email",
  "email.wait_for_verification": "Waited for a verification email",
  "profile.get": "Looked up your saved details",
  "user.ask": "Asked you for a detail",
  "site.report_auth_methods": "Checked how the site lets people sign in",
  "form.complete": "Submitted the form",
  "data.submit_result": "Saved the information it found",
  "registration.get_status": "Checked the task status",
  "registration.mark_complete": "Marked the registration complete",
  "registration.mark_failed": "Reported that registration could not be completed",
  "registration.mark_captcha_required": "Stopped at a CAPTCHA",
  "registration.mark_human_action_required": "Stopped: a manual step is needed",
};

const PAUSE_PREFIX: Record<string, string> = {
  "registration.mark_captcha_required": "Stopped at a CAPTCHA",
  "registration.mark_human_action_required": "Needs a manual step",
};

export function stepLabel(step: RegistrationStep): string {
  const fallback = STEP_LABELS[step.action];
  if (step.detail) {
    const prefix = PAUSE_PREFIX[step.action];
    return prefix ? `${prefix}: ${step.detail}` : step.detail;
  }
  return fallback ?? "Performed an action";
}

/** True when an earlier attempt may already have sent a submission to the site. */
export function mayHaveSubmitted(steps: RegistrationStep[]): boolean {
  return steps.some((s) => s.success && (s.action === "form.complete" || s.action === "registration.mark_complete"));
}

/**
 * The backend's error_message is written for people; error_code is an internal identifier.
 * Only the message is shown as the primary text.
 */
export function friendlyJobError(job: Pick<RegistrationJob, "state" | "error_message">): string {
  if (job.error_message?.trim()) return job.error_message.trim();
  if (job.state === "failed") return "The task stopped without finishing. The timeline shows the last thing the agent did.";
  if (job.state === "expired") return "The task ran out of time before it could finish.";
  return "";
}
