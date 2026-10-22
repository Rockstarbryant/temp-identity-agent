"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ChevronRight, KeyRound, Loader2, Send, Trash2 } from "lucide-react";
import { ApiError, ChatMessageItem, Conversation as Convo } from "@/lib/api";
import { cn } from "@/components/ui/cn";
import Button from "@/components/ui/Button";
import CopyButton from "@/components/ui/CopyButton";
import { inputClass } from "@/components/ui/Field";
import { InlineMessage } from "@/components/ui/States";
import { useConfirm } from "@/components/ui/Feedback";
import { linkify } from "./linkify";
import TaskBlock from "./TaskBlock";

/** How a conversation is loaded, written to and cleared. Lets one component serve every kind of chat. */
export interface ConversationApi {
  load: () => Promise<Convo | null>;
  send: (message: string) => Promise<Convo>;
  clear: () => Promise<void>;
}

const STARTERS = [
  { label: "Sign me up on a website", fill: "Sign me up on " },
  { label: "Fill in an online form", fill: "Fill in this form: " },
  { label: "What can you do?", fill: "What can you do?" },
];
const ACCOUNT_STARTERS = ["Did any email arrive?", "What is my username here?", "Sign in and tell me what my dashboard shows"];

function Actions({ actions }: { actions: ChatMessageItem["actions"] }) {
  if (!actions?.length) return null;
  const summary = actions.map((a) => a.label).join(" · ");
  return (
    <details className="group mb-1.5 text-xs text-muted">
      <summary className="flex cursor-pointer select-none list-none items-center gap-1 hover:text-ink">
        <ChevronRight className="h-3 w-3 transition-transform group-open:rotate-90" aria-hidden="true" />
        <span className="truncate">{summary}</span>
      </summary>
      <ul className="mt-1 space-y-0.5 pl-4">
        {actions.map((a, i) => (
          <li key={i} className={a.ok ? "" : "text-danger"}>{a.ok ? "✓" : "✕"} {a.label}{a.ok ? "" : " (did not work)"}</li>
        ))}
      </ul>
    </details>
  );
}

function Bubble({ m, accountId, onTaskFinished }: { m: ChatMessageItem; accountId: string | null; onTaskFinished: () => void }) {
  const mine = m.role === "user";
  return (
    <div className={cn("group flex flex-col gap-1.5", mine ? "items-end" : "items-start")}>
      <div className={cn("flex max-w-[92%] items-start gap-1", mine && "flex-row-reverse")}>
        <div
          className={cn(
            "min-w-0 whitespace-pre-wrap break-words rounded-lg px-3 py-2 text-sm",
            mine ? "bg-accent-fill text-white" : "border border-line bg-surface text-ink",
          )}
        >
          {!mine && <Actions actions={m.actions} />}
          {m.kind === "task_result" && <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted">Result</p>}
          {linkify(m.content)}
          {m.kind === "task_result" && accountId && (
            <Link href={`/accounts/${accountId}`} className="mt-2 flex items-center gap-1 text-xs font-medium text-accent-strong hover:underline">
              <KeyRound className="h-3 w-3" aria-hidden="true" /> Open in your vault
            </Link>
          )}
        </div>
        <CopyButton value={m.content} label="message" className="mt-0.5 opacity-60 hover:opacity-100 group-hover:opacity-100 md:opacity-0 md:focus:opacity-100" />
      </div>
      {m.kind === "task_started" && m.job_id && (
        <div className="w-full max-w-[92%]"><TaskBlock jobId={m.job_id} onFinished={onTaskFinished} /></div>
      )}
    </div>
  );
}

export default function Conversation({
  api, domain, tall = false, onActivity, resetKey,
}: {
  api: ConversationApi;
  /** Shown in prompts and labels, e.g. the account's domain. Omit for a general chat. */
  domain?: string;
  /** Fill the available height (the Chat page) instead of a fixed-height box. */
  tall?: boolean;
  /** Called when something changed that a conversation list should reflect. */
  onActivity?: (c: Convo | null) => void;
  /** Change to reload (for example when switching conversations). */
  resetKey?: string;
}) {
  const confirm = useConfirm();
  const [chat, setChat] = useState<Convo | null>(null);
  const [missing, setMissing] = useState(false);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef(api);
  apiRef.current = api;
  const activity = useRef(onActivity);
  activity.current = onActivity;

  const load = useCallback(async () => {
    try {
      const c = await apiRef.current.load();
      setChat(c);
      setMissing(c === null);
      activity.current?.(c);
    } catch {
      /* the next poll or action retries */
    }
  }, []);

  useEffect(() => {
    setChat(null);
    setMissing(false);
    setError(null);
    setText("");
    void load();
  }, [load, resetKey]);

  const working = !!chat?.active_job;
  useEffect(() => {
    if (!working) return;
    const t = setInterval(() => void load(), 5000);
    return () => clearInterval(t);
  }, [working, load]);

  const count = chat?.messages.length ?? 0;
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [count, sending]);

  async function send(message: string) {
    const value = message.trim();
    if (!value || sending) return;
    setSending(true);
    setError(null);
    setText("");
    setChat((c) => ({
      ...(c ?? { id: "", title: "", account_id: null, account_status: null, can_chat: true, active_job: null, messages: [] }),
      messages: [...(c?.messages ?? []), { id: "pending", role: "user", kind: "text", content: value, actions: [], job_id: null, created_at: new Date().toISOString() }],
    }));
    try {
      const next = await apiRef.current.send(value);
      setChat(next);
      activity.current?.(next);
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
      title: chat?.account_id ? "Clear this conversation?" : "Delete this chat?",
      description: chat?.account_id
        ? "Only the chat is removed. The account and its mailbox stay as they are."
        : "The chat is removed. Tasks it started stay in Activity, and accounts they created stay in your vault.",
      confirmLabel: chat?.account_id ? "Clear chat" : "Delete chat",
      destructive: true,
    });
    if (!ok) return;
    await apiRef.current.clear();
    await load();
  }

  if (missing) return <InlineMessage tone="info">This conversation no longer exists.</InlineMessage>;
  if (!chat) return <div className="flex justify-center py-6 text-muted"><Loader2 className="h-5 w-5 animate-spin" aria-label="Loading chat" /></div>;

  const empty = chat.messages.length === 0;
  const isAccount = !!chat.account_id;

  return (
    <div className={cn(tall ? "flex h-full min-h-0 flex-col gap-3" : "space-y-3")}>
      <div
        className={cn("space-y-3 overflow-y-auto rounded-md border border-line bg-subtle/50 p-3", tall ? "min-h-0 flex-1" : "max-h-[32rem] min-h-24")}
        role="log" aria-live="polite" aria-label={domain ? `Conversation about ${domain}` : "Conversation"}
      >
        {empty && (
          <div className="space-y-3 py-2 text-sm text-muted">
            {isAccount || domain ? (
              <p>Ask anything about this account. The agent can read its mailbox, change the saved username or password, or sign in to {domain ?? "the site"} and do something for you.</p>
            ) : (
              <p>Tell the agent what to do. Paste a website address to start a sign-up or form task right away, or describe what you need.</p>
            )}
            <div className="flex flex-wrap gap-1.5">
              {(isAccount || domain ? ACCOUNT_STARTERS.map((s) => ({ label: s, fill: "" })) : STARTERS).map((s) => (
                <button key={s.label} type="button" disabled={sending}
                        onClick={() => (s.fill ? setText(s.fill) : void send(s.label))}
                        className="rounded-full border border-line-strong bg-surface px-2.5 py-1 text-xs text-ink hover:bg-subtle disabled:opacity-50">
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {chat.messages.map((m) => (
          <Bubble key={m.id} m={m} accountId={chat.account_id} onTaskFinished={() => void load()} />
        ))}

        {sending && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-xs text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> Thinking…
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {error && <InlineMessage tone="danger">{error}</InlineMessage>}

      {!chat.can_chat && (
        <InlineMessage tone="info">This account has expired, so the agent can no longer act on it. You can still read this conversation.</InlineMessage>
      )}

      <form onSubmit={onSubmit} className={cn("flex items-end gap-2", !chat.can_chat && "hidden")}>
        <label htmlFor="chat-input" className="sr-only">Message to the agent</label>
        <textarea
          id="chat-input" value={text} onChange={(e) => setText(e.target.value)} rows={2} maxLength={2000}
          placeholder={isAccount || domain ? "Message the agent…" : "Paste a website address, or describe a task…"}
          disabled={sending}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(text); } }}
          className={cn(inputClass, "resize-none")}
        />
        <Button type="submit" variant="primary" loading={sending} disabled={!text.trim()} aria-label="Send">
          {!sending && <Send className="h-4 w-4" aria-hidden="true" />}
        </Button>
      </form>

      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted">
        <span>The agent never sees your passwords. Tasks run in a real browser and also appear in Activity.</span>
        {chat.messages.length > 0 && (
          <button type="button" onClick={() => void handleClear()} className="flex items-center gap-1 hover:text-danger">
            <Trash2 className="h-3 w-3" aria-hidden="true" /> {isAccount ? "Clear chat" : "Delete chat"}
          </button>
        )}
      </div>
    </div>
  );
}
