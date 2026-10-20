import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { RegistrationStep } from "@/lib/api";
import { statusMeta, stepLabel } from "@/lib/jobStatus";
import { formatTime } from "@/lib/format";

/**
 * Chronological record of what the agent actually did, from the steps the backend stored.
 * Descriptions are the secret-free `detail` text (or a plain-language label for the action).
 * Raw error text and tool names are available behind a disclosure, never as the main message.
 * Nothing here is invented: the last row is derived from the job's current state.
 */
export default function Timeline({ steps, state }: { steps: RegistrationStep[]; state: string }) {
  const meta = statusMeta(state);
  const inProgress = meta.group === "running" || meta.group === "waiting_email";

  if (steps.length === 0 && !inProgress) {
    return <p className="text-sm text-muted">No steps were recorded for this task.</p>;
  }

  return (
    <ol className="space-y-0">
      {steps.map((step, i) => {
        const last = i === steps.length - 1 && !inProgress;
        return (
          <li key={step.step_index} className="relative flex gap-3 pb-4">
            {!last && <span aria-hidden="true" className="absolute left-[9px] top-5 h-[calc(100%-1rem)] w-px bg-line" />}
            {step.success ? (
              <CheckCircle2 className="relative mt-0.5 h-[18px] w-[18px] shrink-0 bg-surface text-success" aria-label="Succeeded" />
            ) : (
              <XCircle className="relative mt-0.5 h-[18px] w-[18px] shrink-0 bg-surface text-danger" aria-label="Did not succeed" />
            )}
            <div className="min-w-0 flex-1">
              <p className="break-words text-sm text-ink">
                {stepLabel(step)}
                {!step.success && <span className="ml-1.5 text-xs font-medium text-danger">Did not succeed</span>}
              </p>
              <p className="mt-0.5 text-xs text-muted">
                <time dateTime={step.created_at}>{formatTime(step.created_at)}</time>
              </p>
              {(step.error || step.tool_name) && !step.success && (
                <details className="mt-1 text-xs text-muted">
                  <summary className="cursor-pointer select-none hover:text-ink">Technical details</summary>
                  <p className="mt-1 break-words font-mono">
                    {step.tool_name}
                    {step.error ? `: ${step.error}` : ""}
                  </p>
                </details>
              )}
            </div>
          </li>
        );
      })}
      {inProgress && (
        <li className="flex gap-3">
          <Loader2 className="mt-0.5 h-[18px] w-[18px] shrink-0 animate-spin text-accent" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="text-sm text-ink">{meta.label}</p>
            <p className="mt-0.5 text-xs text-muted">{meta.description}</p>
          </div>
        </li>
      )}
    </ol>
  );
}
