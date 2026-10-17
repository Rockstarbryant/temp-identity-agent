import { JobState } from "@/lib/api";

const STYLES: Record<JobState, string> = {
  queued: "bg-black/5 text-black/60",
  starting: "bg-blue-50 text-blue-700",
  opening_site: "bg-blue-50 text-blue-700",
  analyzing: "bg-blue-50 text-blue-700",
  identity_created: "bg-blue-50 text-blue-700",
  filling_form: "bg-blue-50 text-blue-700",
  submitting: "bg-blue-50 text-blue-700",
  waiting_for_email: "bg-amber-50 text-amber-700",
  verifying: "bg-amber-50 text-amber-700",
  waiting_for_user: "bg-amber-50 text-amber-700",
  completed: "bg-green-50 text-green-700",
  captcha_required: "bg-red-50 text-red-700",
  human_action_required: "bg-red-50 text-red-700",
  failed: "bg-red-50 text-red-700",
  cancelled: "bg-black/5 text-black/50",
  expired: "bg-black/5 text-black/50",
};

const LABELS: Record<JobState, string> = {
  queued: "Queued",
  starting: "Starting",
  opening_site: "Opening site",
  analyzing: "Analyzing",
  identity_created: "Identity created",
  filling_form: "Filling form",
  submitting: "Submitting",
  waiting_for_email: "Waiting for email",
  verifying: "Verifying",
  waiting_for_user: "Needs your answer",
  completed: "Completed",
  captcha_required: "CAPTCHA — needs you",
  human_action_required: "Action needed",
  failed: "Failed",
  cancelled: "Cancelled",
  expired: "Expired",
};

export default function StateBadge({ state }: { state: JobState }) {
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${STYLES[state]}`}>
      {LABELS[state]}
    </span>
  );
}
