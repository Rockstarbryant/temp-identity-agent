"use client";

import { useState } from "react";
import { HelpCircle, Loader2, Lock } from "lucide-react";
import { ApiError, PendingQuestion, answerQuestion } from "@/lib/api";

interface Props {
  jobId: string;
  question: PendingQuestion;
  onDone: () => void;
}

/** The agent needs a detail from the user. It waits (browser still open) until this is answered or skipped. */
export default function QuestionCard({ jobId, question, onDone }: Props) {
  const [answer, setAnswer] = useState("");
  const [remember, setRemember] = useState(!question.sensitive && !!question.key);
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

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); send(false); }}
      className="space-y-3 rounded-md border border-amber-200 bg-amber-50 p-4"
    >
      <div className="flex items-center gap-2 font-medium text-amber-900">
        <HelpCircle className="h-4 w-4" /> The agent needs a detail from you
      </div>
      <p className="text-sm text-amber-900">{question.question}</p>

      {question.options.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {question.options.map((o) => (
            <button
              type="button" key={o} onClick={() => setAnswer(o)}
              className={`rounded-full border px-3 py-1 text-sm ${
                answer === o ? "border-accent bg-accent text-white" : "border-black/15 bg-white hover:bg-black/5"
              }`}
            >
              {o}
            </button>
          ))}
        </div>
      ) : (
        <div className="relative">
          {question.sensitive && <Lock className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-black/30" />}
          <input
            autoFocus value={answer} onChange={(e) => setAnswer(e.target.value)} maxLength={1000}
            placeholder="Your answer" autoComplete="off"
            className={`w-full rounded-md border border-black/15 bg-white py-2 pr-3 text-sm ${question.sensitive ? "pl-8" : "pl-3"}`}
          />
        </div>
      )}

      {question.key && (
        <label className="flex items-center gap-2 text-xs text-amber-900">
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
          Remember this next time
          {question.sensitive && <span className="text-amber-900/70">(stored encrypted)</span>}
        </label>
      )}
      {question.sensitive && <p className="text-xs text-amber-900/70">This answer is hidden in the job timeline.</p>}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit" disabled={busy !== null || !answer.trim()}
          className="flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-50"
        >
          {busy === "answer" && <Loader2 className="h-4 w-4 animate-spin" />} Send answer
        </button>
        <button
          type="button" onClick={() => send(true)} disabled={busy !== null}
          className="text-sm text-amber-900/80 underline disabled:opacity-50"
        >
          {busy === "skip" ? "Skipping…" : "I'd rather not say"}
        </button>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </form>
  );
}
