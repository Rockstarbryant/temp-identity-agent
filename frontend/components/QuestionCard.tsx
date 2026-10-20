"use client";

import { useState } from "react";
import { Eye, EyeOff, HelpCircle, Lock } from "lucide-react";
import { ApiError, PendingQuestion, answerQuestion } from "@/lib/api";
import Button from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import { InlineMessage } from "@/components/ui/States";
import { cn } from "@/components/ui/cn";

interface Props {
  jobId: string;
  question: PendingQuestion;
  onDone: () => void;
}

/**
 * The agent needs a detail only the user has. The task waits until this is answered or skipped.
 * Sensitive questions use a masked field, and their answers are hidden from the task timeline.
 */
export default function QuestionCard({ jobId, question, onDone }: Props) {
  const [answer, setAnswer] = useState("");
  const [remember, setRemember] = useState(!question.sensitive && !!question.key);
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState<"answer" | "skip" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function send(skip: boolean) {
    if (!skip && !answer.trim()) return;
    setBusy(skip ? "skip" : "answer");
    setError(null);
    try {
      await answerQuestion(jobId, question.id, skip ? { skip: true } : { answer: answer.trim(), remember });
      onDone();
    } catch (err) {
      const body = err instanceof ApiError ? (err.body as { detail?: string } | undefined) : undefined;
      setError(body?.detail || "Could not send your answer.");
    } finally {
      setBusy(null);
    }
  }

  const legendId = `q-${question.id}`;

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); void send(false); }}
      className="space-y-3 rounded-lg border border-warning-line bg-warning-soft p-4"
    >
      <div className="flex items-center gap-2 text-sm font-semibold text-warning">
        <HelpCircle className="h-4 w-4" aria-hidden="true" /> The agent needs a detail from you
      </div>
      <p id={legendId} className="text-sm text-ink">{question.question}</p>

      {question.options.length > 0 ? (
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-labelledby={legendId}>
          {question.options.map((o) => (
            <button
              type="button" key={o} role="radio" aria-checked={answer === o} onClick={() => setAnswer(o)}
              className={cn(
                "rounded-md border px-3 py-1.5 text-sm transition-colors",
                answer === o ? "border-accent-strong bg-accent-strong text-white" : "border-line-strong bg-surface hover:bg-subtle",
              )}
            >
              {o}
            </button>
          ))}
        </div>
      ) : (
        <Field
          label="Your answer"
          hideLabel
          autoFocus
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          maxLength={1000}
          placeholder="Your answer"
          autoComplete="off"
          type={question.sensitive && !show ? "password" : "text"}
          trailing={
            question.sensitive ? (
              <button
                type="button" onClick={() => setShow((s) => !s)}
                aria-label={show ? "Hide answer" : "Show answer"}
                className="rounded p-1.5 text-muted hover:bg-subtle hover:text-ink"
              >
                {show ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
              </button>
            ) : undefined
          }
        />
      )}

      {question.key && (
        <label className="flex items-center gap-2 text-xs text-ink">
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="h-4 w-4 accent-accent-strong" />
          Remember this for next time
          {question.sensitive && <span className="text-muted">(stored encrypted)</span>}
        </label>
      )}
      {question.sensitive && (
        <p className="flex items-center gap-1.5 text-xs text-muted">
          <Lock className="h-3 w-3" aria-hidden="true" /> This answer is hidden in the task timeline.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" variant="primary" loading={busy === "answer"} disabled={busy !== null || !answer.trim()}>
          Send answer
        </Button>
        <Button variant="ghost" onClick={() => void send(true)} loading={busy === "skip"} disabled={busy !== null}>
          I would rather not say
        </Button>
      </div>
      {error && <InlineMessage tone="danger">{error}</InlineMessage>}
    </form>
  );
}
