"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import {
  ArrowLeft, Bell, BellOff, ExternalLink, Loader2, Mail, MailOpen, RefreshCw, Send, Sparkles,
} from "lucide-react";
import {
  ApiError, Mailbox, MailMessage, askInbox, askMailbox, getInbox, getInboxMessage, getMailbox, getMailMessage, setEmailMuted,
} from "@/lib/api";
import { formatDateTime, hostOf, isSafeHttpUrl, timeAgo } from "@/lib/format";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import CopyButton from "@/components/ui/CopyButton";
import { inputClass } from "@/components/ui/Field";
import { InlineMessage } from "@/components/ui/States";
import { cn } from "@/components/ui/cn";

/** Where a mailbox view gets its data: one vault account's mailbox, or the connected inbox. */
interface MailSource {
  key: string;
  load: (refresh: boolean) => Promise<Mailbox>;
  message: (id: string) => Promise<MailMessage>;
  ask: (question: string) => Promise<{ answer: string }>;
  /** Present for the connected inbox only. */
  setMuted?: (muted: boolean) => Promise<unknown>;
}

const accountSource = (accountId: string): MailSource => ({
  key: `account:${accountId}`,
  load: (refresh) => getMailbox(accountId, refresh),
  message: (id) => getMailMessage(accountId, id),
  ask: (q) => askMailbox(accountId, q),
});

const inboxSource: MailSource = {
  key: "inbox",
  load: (refresh) => getInbox(refresh),
  message: (id) => getInboxMessage(id),
  ask: (q) => askInbox(q),
  setMuted: (m) => setEmailMuted(m),
};

/** Verification code and link for one message. Shown only when the backend extracted them. */
function VerificationPanel({ msg }: { msg: MailMessage }) {
  const link = msg.verification_link && isSafeHttpUrl(msg.verification_link) ? msg.verification_link : "";
  if (!msg.code && !link) {
    return <p className="text-xs text-muted">No verification code or link was found in this message.</p>;
  }
  return (
    <div className="space-y-3 rounded-lg border border-accent/30 bg-accent-soft p-3">
      {msg.code && (
        <div>
          <p className="text-xs font-medium text-muted">Verification code</p>
          <div className="mt-1 flex items-center gap-2">
            <code className="min-w-0 break-all rounded-md border border-line bg-surface px-3 py-1.5 font-mono text-lg font-semibold tracking-wider">
              {msg.code}
            </code>
            <CopyButton value={msg.code} label="verification code" withText />
          </div>
        </div>
      )}
      {link && (
        <div>
          <p className="text-xs font-medium text-muted">Verification link</p>
          <a
            href={link}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="mt-1 inline-flex max-w-full items-center gap-1.5 rounded-md bg-accent-fill px-3 py-2 text-sm font-medium text-white hover:bg-accent-fill/90"
          >
            <ExternalLink className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span className="truncate">Open link on {hostOf(link) || "the site"}</span>
            <span className="sr-only">(opens in a new tab)</span>
          </a>
          <p className="mt-1 text-xs text-muted">Only open this if you started the sign-up it belongs to.</p>
        </div>
      )}
    </div>
  );
}

function MessageReader({
  source, id, onRead, onBack,
}: { source: MailSource; id: string; onRead: (id: string) => void; onBack: () => void }) {
  const [msg, setMsg] = useState<MailMessage | null>(null);
  const [error, setError] = useState("");
  const onReadRef = useRef(onRead);
  onReadRef.current = onRead;

  useEffect(() => {
    let live = true;
    setMsg(null);
    setError("");
    source.message(id)
      .then((m) => {
        if (!live) return;
        setMsg(m);
        onReadRef.current(id);
      })
      .catch(() => live && setError("Could not open this message."));
    return () => {
      live = false;
    };
  }, [source, id]);

  return (
    <div className="flex min-w-0 flex-col">
      <button
        type="button"
        onClick={onBack}
        className="mb-3 inline-flex items-center gap-1 self-start text-xs text-muted hover:text-ink lg:hidden"
      >
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> Back to messages
      </button>
      {error ? (
        <InlineMessage tone="danger">{error}</InlineMessage>
      ) : !msg ? (
        <p role="status" className="flex items-center gap-2 py-6 text-sm text-muted">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Opening message
        </p>
      ) : (
        <article className="space-y-4">
          <header>
            <h3 className="break-words text-base font-semibold">{msg.subject || "(no subject)"}</h3>
            <p className="mt-1 break-all text-xs text-muted">
              From <span className="font-mono">{msg.sender}</span>
              {msg.received_at && <> · {formatDateTime(msg.received_at)}</>}
            </p>
          </header>
          <VerificationPanel msg={msg} />
          {/* Email text is rendered as plain text only. HTML is never injected into the page. */}
          <pre className="max-h-[28rem] overflow-auto whitespace-pre-wrap break-words rounded-md border border-line bg-subtle p-3 font-sans text-sm text-ink">
            {msg.text || "(This message has no text content.)"}
          </pre>
          {msg.links.filter(isSafeHttpUrl).length > 0 && (
            <details className="text-xs">
              <summary className="cursor-pointer select-none text-muted hover:text-ink">
                All links in this message ({msg.links.filter(isSafeHttpUrl).length})
              </summary>
              <ul className="mt-2 space-y-1.5">
                {msg.links.filter(isSafeHttpUrl).map((l) => (
                  <li key={l} className="break-all font-mono">
                    <a href={l} target="_blank" rel="noopener noreferrer nofollow" className="text-accent-strong hover:underline">
                      {l}
                    </a>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </article>
      )}
    </div>
  );
}

const SUGGESTIONS = ["Did the verification email arrive?", "What is the code?", "Summarize what is in here"];

function Assistant({ source }: { source: MailSource }) {
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<{ q: string; a: string; failed?: boolean } | null>(null);
  const id = useId();

  async function ask(q: string) {
    const text = q.trim();
    if (text.length < 3 || asking) return;
    setAsking(true);
    setAnswer(null);
    try {
      const r = await source.ask(text);
      setAnswer({ q: text, a: r.answer });
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.status === 429 ? "You have asked a lot of questions recently. Try again in a minute." : e.message
          : "The assistant could not answer right now.";
      setAnswer({ q: text, a: msg, failed: true });
    } finally {
      setAsking(false);
    }
  }

  return (
    <details className="rounded-lg border border-line bg-surface">
      <summary className="flex cursor-pointer select-none items-center gap-2 px-3 py-2.5 text-sm font-medium hover:bg-subtle">
        <Sparkles className="h-4 w-4 text-accent" aria-hidden="true" /> Ask the mailbox assistant
      </summary>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask(question);
        }}
        className="space-y-2 border-t border-line p-3"
      >
        <label htmlFor={id} className="text-xs text-muted">The assistant reads {source.setMuted ? "your recent inbox" : "this mailbox"} and answers in plain language.</label>
        <div className="flex gap-2">
          <input
            id={id} value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={300}
            placeholder="Did the verification email arrive?" className={inputClass}
          />
          <Button type="submit" variant="primary" loading={asking} disabled={question.trim().length < 3}>
            {!asking && <Send className="h-4 w-4" aria-hidden="true" />} Ask
          </Button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((q) => (
            <button
              type="button" key={q} disabled={asking}
              onClick={() => { setQuestion(q); void ask(q); }}
              className="rounded-md border border-line-strong px-2 py-1 text-xs text-muted hover:bg-subtle hover:text-ink disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
        {answer && (
          <div role="status" className={cn("rounded-md border p-3 text-sm", answer.failed ? "border-danger-line bg-danger-soft" : "border-line bg-subtle")}>
            <p className="text-xs text-muted">You asked: {answer.q}</p>
            <p className="mt-1 whitespace-pre-wrap break-words">{answer.a}</p>
          </div>
        )}
      </form>
    </details>
  );
}

/**
 * The mailbox for one vault account: message list, reader, verification code and link,
 * manual refresh and the assistant. On wide screens the list and reader sit side by side;
 * on phones it is a list that opens into the reader.
 *
 * The mailbox is checked once when it opens (as before) and again only when the user asks.
 * There is no background polling.
 */
export default function MailboxPanel({ accountId }: { accountId: string }) {
  const source = useMemo(() => accountSource(accountId), [accountId]);
  return <MailboxView source={source} />;
}

/** Your connected Gmail / IMAP inbox as one inbox: every task's mail in one list, one mute switch. */
export function InboxPanel() {
  return <MailboxView source={inboxSource} />;
}

function MailboxView({ source }: { source: MailSource }) {
  const [muting, setMuting] = useState(false);
  const [box, setBox] = useState<Mailbox | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [error, setError] = useState<{ text: string; retry: boolean } | null>(null);
  const loadedFor = useRef<string | null>(null);

  const load = useCallback(async (refresh: boolean) => {
    if (refresh) setRefreshing(true);
    try {
      setBox(await source.load(refresh));
      setError(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setError({ text: source.setMuted ? "No email is connected. Connect one in Settings." : "This account has no mailbox.", retry: false });
      }
      else if (e instanceof ApiError && e.status === 410) setError({ text: "This account was deleted, so its mailbox is gone.", retry: false });
      else setError({ text: "Could not load the mailbox.", retry: true });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [source]);

  useEffect(() => {
    if (loadedFor.current === source.key) return; // StrictMode runs effects twice in development
    loadedFor.current = source.key;
    setBox(null);
    setOpenId(null);
    setLoading(true);
    void load(true);
  }, [source, load]);

  const markReadLocally = useCallback((id: string) => {
    setBox((b) =>
      b && {
        ...b,
        unread: b.messages.some((m) => m.id === id && !m.read) ? Math.max(0, b.unread - 1) : b.unread,
        messages: b.messages.map((m) => (m.id === id ? { ...m, read: true } : m)),
      },
    );
  }, []);

  if (loading) {
    return (
      <p role="status" className="flex items-center gap-2 py-6 text-sm text-muted">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Checking the mailbox
      </p>
    );
  }
  if (error && !box) {
    return (
      <div className="space-y-3">
        <InlineMessage tone="danger">{error.text}</InlineMessage>
        {error.retry && <Button size="sm" onClick={() => { setLoading(true); void load(true); }}>Try again</Button>}
      </div>
    );
  }
  if (!box) return null;

  const closed = box.mailbox.status === "closed";
  const muted = !!box.mailbox.muted;

  async function toggleMute() {
    if (!source.setMuted) return;
    setMuting(true);
    try {
      await source.setMuted(!muted);
      setBox((b) => b && { ...b, mailbox: { ...b.mailbox, muted: !muted } });
      setError(null);
    } catch {
      setError({ text: "Could not change the mute setting.", retry: false });
    } finally {
      setMuting(false);
    }
  }

  return (
    <section className="space-y-4" aria-label="Mailbox">
      {/* Mailbox details */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1.5">
          <div className="flex min-w-0 items-center gap-1">
            <span className="min-w-0 break-all font-mono text-sm">{box.mailbox.address}</span>
            <CopyButton value={box.mailbox.address} label="mailbox address" />
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone={closed ? "neutral" : "success"}>{closed ? "Closed" : "Active"}</Badge>
            {box.mailbox.own_inbox && <Badge>Your own inbox</Badge>}
            {muted && <Badge tone="warning" icon={<BellOff className="h-3 w-3" aria-hidden="true" />}>Muted</Badge>}
            {box.unread > 0 && <Badge tone="accent">{box.unread} unread</Badge>}
          </div>
          <p className="text-xs text-muted">
            {!box.mailbox.own_inbox && box.mailbox.expires_at && <>Mailbox expires {formatDateTime(box.mailbox.expires_at)}. </>}
            {box.mailbox.last_checked_at ? <>Last checked {timeAgo(box.mailbox.last_checked_at)}.</> : "Not checked yet."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {source.setMuted && (
            <Button size="sm" onClick={() => void toggleMute()} loading={muting}>
              {!muting && (muted ? <Bell className="h-4 w-4" aria-hidden="true" /> : <BellOff className="h-4 w-4" aria-hidden="true" />)}
              {muted ? "Unmute" : "Mute"}
            </Button>
          )}
          <Button size="sm" onClick={() => void load(true)} loading={refreshing} disabled={closed}>
            {!refreshing && <RefreshCw className="h-4 w-4" aria-hidden="true" />} Check now
          </Button>
        </div>
      </div>

      {muted && (
        <InlineMessage tone="info">
          Muted: no background checks and no &ldquo;new email&rdquo; notifications for this inbox. The agent still reads it
          while a task is running, and Check now still works.
        </InlineMessage>
      )}

      {closed && (
        <InlineMessage tone="info">This mailbox is closed, so new mail cannot arrive. Messages already saved are still shown.</InlineMessage>
      )}
      {box.refresh_error && <InlineMessage tone="warning">{box.refresh_error}</InlineMessage>}
      {error && <InlineMessage tone="danger">{error.text}</InlineMessage>}

      <Assistant source={source} />

      {/* Messages */}
      {box.messages.length === 0 ? (
        <div className="rounded-lg border border-dashed border-line-strong px-4 py-8 text-center">
          <p className="text-sm font-medium">No messages yet</p>
          <p className="mt-1 text-sm text-muted">
            {closed ? "Nothing was received before this mailbox closed."
              : source.setMuted ? "Mail that arrives after your first permanent-account task appears here."
              : "Verification emails appear here. You will also get a notification when one arrives."}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,19rem)_minmax(0,1fr)]">
          <ul className={cn("divide-y divide-line self-start overflow-hidden rounded-lg border border-line bg-surface", openId && "hidden lg:block")}>
            {box.messages.map((m) => {
              const active = openId === m.id;
              return (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => setOpenId(m.id)}
                    aria-current={active ? "true" : undefined}
                    className={cn("flex w-full items-start gap-2.5 px-3 py-3 text-left hover:bg-subtle", active && "bg-accent-soft hover:bg-accent-soft")}
                  >
                    {m.read ? (
                      <MailOpen className="mt-0.5 h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
                    ) : (
                      <Mail className="mt-0.5 h-4 w-4 shrink-0 text-accent-strong" aria-hidden="true" />
                    )}
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline justify-between gap-2">
                        <span className={cn("truncate text-sm", m.read ? "text-ink/80" : "font-semibold")}>
                          {!m.read && <span className="sr-only">Unread: </span>}
                          {m.subject || "(no subject)"}
                        </span>
                        <span className="shrink-0 text-[11px] text-muted">{timeAgo(m.received_at)}</span>
                      </span>
                      <span className="block truncate font-mono text-xs text-muted">{m.sender}</span>
                      <span className="block truncate text-xs text-muted">{m.snippet}</span>
                      {(m.has_code || m.has_link || m.site) && (
                        <span className="mt-1 flex flex-wrap gap-1">
                          {m.site && <Badge>{m.site}</Badge>}
                          {m.has_code && <Badge tone="accent">Code</Badge>}
                          {m.has_link && <Badge tone="accent">Link</Badge>}
                        </span>
                      )}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>

          <div className={cn("min-w-0 rounded-lg border border-line bg-surface p-4", !openId && "hidden lg:block")}>
            {openId ? (
              <MessageReader source={source} id={openId} onRead={markReadLocally} onBack={() => setOpenId(null)} />
            ) : (
              <p className="py-10 text-center text-sm text-muted">Select a message to read it.</p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
