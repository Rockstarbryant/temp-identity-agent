"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, Loader2, Send, Trash2 } from "lucide-react";
import { AccountChat as Chat, ApiError, clearAccountChat, getAccountChat, sendAccountChat } from "@/lib/api";
import { cn } from "@/components/ui/cn";
import Button from "@/components/ui/Button";
import { inputClass } from "@/components/ui/Field";
import { InlineMessage } from "@/components/ui/States";
import { useConfirm } from "@/components/ui/Feedback";

const SUGGESTIONS = [
  "Did any email arrive?",
  "What is my username here?",
  "Sign in and tell me what my dashboard shows",
];

export default function AccountChat({ accountId, domain }: { accountId: string; domain: string }) {
  const confirm = useConfirm();
  const [chat, setChat] = useState<Chat | null>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const messageCount = chat?.messages.length ?? 0;

  const load = useCallback(async () => {
    try {
      setChat(await getAccountChat(accountId));
    } catch {
      /* the next poll or action retries */
    }
  }, [accountId]);

  useEffect(() => {
    void load();
  }, [load]);

  // While the agent is working on the website, check for its result.
  const working = !!chat?.active_job;
  useEffect(() => {
    if (!working) return;
    const t = setInterval(() => void load(), 4000);
    return () => clearInterval(t);
  }, [working, load]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [messageCount, sending]);

  async function send(message: string) {
    const value = message.trim();
    if (!value || sending) return;
    setSending(true);
    setError(null);
    setText("");
    // Show the user's message straight away; the server's copy replaces it.
    setChat((c) => c && {
      ...c,
      messages: [...c.messages, { id: "pending", role: "user", kind: "text", content: value, job_id: null, created_at: new Date().toISOString() }],
    });
    try {
      setChat(await sendAccountChat(accountId, value));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The agent could not answer. Try again.");
      setText(value);
      await load();
    } finally {
      setSending(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send(text);
  }

  async function handleClear() {
    const ok = await confirm({
      title: "Clear this conversation?",
      description: "Only the chat is removed. The account and its mailbox stay as they are.",
      confirmLabel: "Clear chat",
      destructive: true,
    });
    if (!ok) return;
    await clearAccountChat(accountId);
    await load();
  }

  if (!chat) return <div className="flex justify-center py-6 text-muted"><Loader2 className="h-5 w-5 animate-spin" aria-label="Loading chat" /></div>;

  return (
    <div className="space-y-3">
      <div
        className="max-h-[28rem] min-h-24 space-y-2.5 overflow-y-auto rounded-md border border-line bg-subtle/50 p-3"
        role="log" aria-live="polite" aria-label={`Conversation about ${domain}`}
      >
        {chat.messages.length === 0 && (
          <div className="space-y-2 py-2 text-sm text-muted">
            <p>Ask anything about this account. The agent can read its mailbox, change the saved username or password, or sign in to {domain} and do something for you.</p>
            <div className="flex flex-wrap gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" onClick={() => void send(s)} disabled={sending}
                        className="rounded-full border border-line-strong bg-surface px-2.5 py-1 text-xs text-ink hover:bg-subtle disabled:opacity-50">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {chat.messages.map((m) => (
          <div key={m.id} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
            <div className={cn(
              "max-w-[88%] whitespace-pre-wrap break-words rounded-lg px-3 py-2 text-sm",
              m.role === "user" ? "bg-accent-fill text-white" : "border border-line bg-surface text-ink",
            )}>
              {m.kind === "task_result" && <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted">Result from {domain}</p>}
              {m.content}
              {m.job_id && (
                <Link href={`/jobs/${m.job_id}`} className="mt-1.5 flex items-center gap-1 text-xs font-medium text-accent-strong hover:underline">
                  <ExternalLink className="h-3 w-3" aria-hidden="true" /> {m.kind === "task_started" ? "Watch the task" : "Open the task"}
                </Link>
              )}
            </div>
          </div>
        ))}

        {(sending || working) && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-xs text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              {sending ? "Thinking…" : `Working on ${domain}. The result will appear here.`}
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {error && <InlineMessage tone="danger">{error}</InlineMessage>}

      <form onSubmit={onSubmit} className="flex items-end gap-2">
        <label htmlFor="account-chat-input" className="sr-only">Message to the agent</label>
        <textarea
          id="account-chat-input" value={text} onChange={(e) => setText(e.target.value)} rows={2} maxLength={2000}
          placeholder="Message the agent…" disabled={sending}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(text); } }}
          className={cn(inputClass, "resize-none")}
        />
        <Button type="submit" variant="primary" loading={sending} disabled={!text.trim()} aria-label="Send">
          {!sending && <Send className="h-4 w-4" aria-hidden="true" />}
        </Button>
      </form>

      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted">
        <span>The agent never sees your password. Website tasks run in a real browser and show up in Activity.</span>
        {chat.messages.length > 0 && (
          <button type="button" onClick={() => void handleClear()} className="flex items-center gap-1 hover:text-danger">
            <Trash2 className="h-3 w-3" aria-hidden="true" /> Clear chat
          </button>
        )}
      </div>
    </div>
  );
}
