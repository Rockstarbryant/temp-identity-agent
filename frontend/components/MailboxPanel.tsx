"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Copy, ExternalLink, Loader2, Mail, MailOpen, RefreshCw, Send, Sparkles } from "lucide-react";
import {
  ApiError, Mailbox, MailMessage, askMailbox, getMailbox, getMailMessage,
} from "@/lib/api";

function when(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function CopyChip({ value, label }: { value: string; label: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(value);
        setDone(true);
        setTimeout(() => setDone(false), 1500);
      }}
      className="flex items-center gap-1 rounded-md bg-black/5 px-2 py-1 text-xs hover:bg-black/10"
    >
      {done ? <Check className="h-3 w-3 text-green-600" /> : <Copy className="h-3 w-3" />} {label}
    </button>
  );
}

function MessageView({ accountId, id, onRead }: { accountId: string; id: string; onRead: () => void }) {
  const [msg, setMsg] = useState<MailMessage | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    getMailMessage(accountId, id)
      .then((m) => {
        if (live) {
          setMsg(m);
          onRead();
        }
      })
      .catch(() => live && setError("Could not open this message."));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId, id]);

  if (error) return <p className="px-3 py-2 text-xs text-red-600">{error}</p>;
  if (!msg) return <div className="flex justify-center p-3 text-black/40"><Loader2 className="h-4 w-4 animate-spin" /></div>;
  return (
    <div className="space-y-2 border-t border-black/10 bg-black/[0.02] px-3 py-3">
      <div className="flex flex-wrap gap-2">
        {msg.code && <CopyChip value={msg.code} label={`Code ${msg.code}`} />}
        {msg.verification_link && (
          <a href={msg.verification_link} target="_blank" rel="noopener noreferrer nofollow"
             className="flex items-center gap-1 rounded-md bg-accent px-2 py-1 text-xs font-medium text-white hover:bg-accent/90">
            <ExternalLink className="h-3 w-3" /> Open verification link
          </a>
        )}
      </div>
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs text-black/70">{msg.text || "(no text)"}</pre>
      {msg.links.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-black/50">All links ({msg.links.length})</summary>
          <ul className="mt-1 space-y-1">
            {msg.links.map((l) => (
              <li key={l} className="break-all">
                <a href={l} target="_blank" rel="noopener noreferrer nofollow" className="text-accent hover:underline">{l}</a>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

export default function MailboxPanel({ accountId }: { accountId: string }) {
  const [box, setBox] = useState<Mailbox | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<{ q: string; a: string } | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    try {
      setBox(await getMailbox(accountId, refresh));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError && e.status === 404 ? "This account has no mailbox." : "Could not load the mailbox.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [accountId]);

  useEffect(() => {
    void load(true);
  }, [load]);

  async function ask(q: string) {
    const text = q.trim();
    if (text.length < 3) return;
    setAsking(true);
    setAnswer(null);
    try {
      const r = await askMailbox(accountId, text);
      setAnswer({ q: text, a: r.answer });
      void load(false);
    } catch (e) {
      setAnswer({ q: text, a: e instanceof ApiError ? e.message : "The agent couldn't answer right now." });
    } finally {
      setAsking(false);
    }
  }

  function markReadLocally(id: string) {
    setBox((b) => b && ({
      ...b,
      unread: b.messages.some((m) => m.id === id && !m.read) ? b.unread - 1 : b.unread,
      messages: b.messages.map((m) => (m.id === id ? { ...m, read: true } : m)),
    }));
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-medium text-black/70">
          <Mail className="h-4 w-4" /> Mailbox
          {box && box.unread > 0 && <span className="rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">{box.unread} new</span>}
        </h2>
        <button onClick={() => load(true)} disabled={refreshing} className="flex items-center gap-1 text-xs text-black/50 hover:text-accent disabled:opacity-50">
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} /> Check now
        </button>
      </div>

      {loading && <div className="flex justify-center py-4 text-black/40"><Loader2 className="h-5 w-5 animate-spin" /></div>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {box && (
        <>
          <p className="break-all text-xs text-black/40">
            {box.mailbox.address}
            {box.mailbox.status === "closed" && " · closed (new mail can't arrive any more)"}
            {box.mailbox.last_checked_at && ` · checked ${when(box.mailbox.last_checked_at)}`}
          </p>
          {box.refresh_error && <p className="text-xs text-amber-700">{box.refresh_error}</p>}

          <form onSubmit={(e) => { e.preventDefault(); void ask(question); }} className="space-y-2 rounded-md border border-accent/20 bg-accent/5 p-3">
            <label htmlFor="mailbox-q" className="flex items-center gap-1.5 text-xs font-medium text-accent">
              <Sparkles className="h-3.5 w-3.5" /> Ask the agent about this mailbox
            </label>
            <div className="flex gap-2">
              <input
                id="mailbox-q" value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={300}
                placeholder="Did the verification email arrive?"
                className="min-w-0 flex-1 rounded-md border border-black/15 bg-white px-3 py-1.5 text-sm"
              />
              <button disabled={asking || question.trim().length < 3}
                      className="flex items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-50">
                {asking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Ask
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {["Did the verification email arrive?", "What is the code?", "Summarize what's in here"].map((q) => (
                <button type="button" key={q} onClick={() => { setQuestion(q); void ask(q); }} disabled={asking}
                        className="rounded-full border border-accent/30 px-2 py-0.5 text-[11px] text-accent hover:bg-accent/10 disabled:opacity-50">
                  {q}
                </button>
              ))}
            </div>
            {answer && (
              <div className="rounded-md bg-white p-3 text-sm">
                <p className="text-[11px] text-black/40">You asked: {answer.q}</p>
                <p className="mt-1 whitespace-pre-wrap break-words">{answer.a}</p>
              </div>
            )}
          </form>

          {box.messages.length === 0 ? (
            <p className="rounded-md border border-dashed border-black/15 p-4 text-center text-sm text-black/40">
              Nothing has arrived yet. You&apos;ll be notified when something does.
            </p>
          ) : (
            <ul className="divide-y divide-black/10 overflow-hidden rounded-md border border-black/10 bg-white">
              {box.messages.map((m) => (
                <li key={m.id}>
                  <button onClick={() => setOpen(open === m.id ? null : m.id)} className="flex w-full items-start gap-2 px-3 py-2.5 text-left hover:bg-black/[0.02]">
                    {m.read ? <MailOpen className="mt-0.5 h-4 w-4 shrink-0 text-black/30" /> : <Mail className="mt-0.5 h-4 w-4 shrink-0 text-accent" />}
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline justify-between gap-2">
                        <span className={`truncate text-sm ${m.read ? "text-black/70" : "font-semibold"}`}>{m.subject || "(no subject)"}</span>
                        <span className="shrink-0 text-[11px] text-black/40">{when(m.received_at)}</span>
                      </span>
                      <span className="block truncate text-xs text-black/50">{m.sender}</span>
                      <span className="block truncate text-xs text-black/40">{m.snippet}</span>
                    </span>
                  </button>
                  {open === m.id && <MessageView accountId={accountId} id={m.id} onRead={() => markReadLocally(m.id)} />}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
