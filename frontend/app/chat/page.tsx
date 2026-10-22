"use client";

import Link from "next/link";
import { Suspense, useCallback, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, KeyRound, Loader2, Mail, MessageSquarePlus, Search } from "lucide-react";
import { ChatSummary, Conversation as Convo, createChat, deleteChat, getChat, listChats, sendChat } from "@/lib/api";
import { invalidate } from "@/lib/cache";
import { useCachedData } from "@/lib/useCachedData";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { timeAgo } from "@/lib/format";
import Conversation, { ConversationApi } from "@/components/chat/Conversation";
import { buttonClass } from "@/components/ui/Button";
import { inputClass } from "@/components/ui/Field";
import { cn } from "@/components/ui/cn";
import { ErrorState, PageSpinner } from "@/components/ui/States";

const CACHE_KEY = "chats";

function ThreadRow({ chat, active, onOpen }: { chat: ChatSummary; active: boolean; onOpen: () => void }) {
  const last = chat.last_message;
  const isAccount = !!chat.account_id;
  return (
    <li>
      <button
        type="button" onClick={onOpen} aria-current={active ? "true" : undefined}
        className={cn("flex w-full items-start gap-3 border-b border-line px-3 py-3 text-left transition-colors", active ? "bg-accent-soft" : "hover:bg-subtle")}
      >
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-subtle text-xs font-semibold uppercase text-muted" aria-hidden="true">
          {isAccount ? chat.title.replace(/^(www|account|app)\./, "").charAt(0) : <MessageSquarePlus className="h-4 w-4" />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-2">
            <span className={cn("truncate text-sm", isAccount && "font-mono", active ? "font-semibold text-accent-strong" : "font-medium text-ink")}>{chat.title}</span>
            <span className="shrink-0 text-[11px] text-muted">{last ? timeAgo(last.created_at) : ""}</span>
          </span>
          <span className="mt-0.5 flex items-center gap-1.5 text-xs text-muted">
            {chat.working && <Loader2 className="h-3 w-3 shrink-0 animate-spin text-accent" aria-label="Working" />}
            <span className="truncate">
              {last ? `${last.role === "user" ? "You: " : ""}${last.content}` : chat.status === "expired" ? "Expired" : "No messages yet"}
            </span>
          </span>
          {chat.status === "expired" && last && <span className="mt-1 inline-block rounded bg-subtle px-1.5 py-0.5 text-[10px] text-muted">Expired</span>}
        </span>
      </button>
    </li>
  );
}

function ChatInner() {
  const ready = useRequireAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [query, setQuery] = useState("");
  const [header, setHeader] = useState<Pick<Convo, "id" | "title" | "account_id"> | null>(null);
  const { data, error, loading, refresh } = useCachedData(ready ? CACHE_KEY : null, async () => (await listChats()).results, { refreshMs: 15000 });

  const chats = useMemo(() => data ?? [], [data]);
  const wantedChat = params.get("c");
  const wantedAccount = params.get("account");
  const byAccount = wantedAccount ? chats.find((c) => c.account_id === wantedAccount) : undefined;
  const selectedId = wantedChat ?? byAccount?.id ?? null;
  const explicitNew = params.get("new") === "1";
  // With nothing selected, desktop shows an empty new chat (like other AI clients); a phone shows the list.
  const isNew = !selectedId && (explicitNew || wantedAccount === null);
  const selected = chats.find((c) => c.id === selectedId) ?? null;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? chats.filter((c) => c.title.toLowerCase().includes(q) || c.email.toLowerCase().includes(q)) : chats;
  }, [chats, query]);

  const open = (id: string) => router.replace(`/chat?c=${id}`);
  const startNew = () => router.replace("/chat?new=1");

  // One adapter per open conversation. A new chat only exists on the server once its first message is sent.
  const api: ConversationApi | null = useMemo(() => {
    if (selectedId) {
      return {
        load: async () => {
          try {
            return await getChat(selectedId);
          } catch (e) {
            if ((e as { status?: number }).status === 404) return null;
            throw e;
          }
        },
        send: (m) => sendChat(selectedId, m),
        clear: async () => {
          const c = chats.find((x) => x.id === selectedId);
          await deleteChat(selectedId);
          invalidate("chats");
          if (!c?.account_id) router.replace("/chat?new=1");
        },
      };
    }
    if (!isNew) return null;
    return {
      load: async () => ({ id: "", title: "New chat", account_id: null, account_status: null, can_chat: true, messages: [], active_job: null }),
      send: async (m) => {
        const created = await createChat();
        const next = await sendChat(created.id, m);
        invalidate("chats");
        router.replace(`/chat?c=${created.id}`);
        return next;
      },
      clear: async () => undefined,
    };
  }, [selectedId, isNew, chats, router]);

  const onActivity = useCallback((c: Convo | null) => {
    if (c) setHeader({ id: c.id, title: c.title, account_id: c.account_id });
    void refresh();
  }, [refresh]);

  if (!ready || (loading && !error)) return <PageSpinner />;
  if (error && !data) return <ErrorState title="Could not load your chats" message="Check your connection and try again." onRetry={() => void refresh()} />;

  const showThread = !!selectedId || explicitNew; // phone: thread instead of list
  const title = selected?.title ?? (header && header.id === selectedId ? header.title : isNew ? "New chat" : "Chat");
  const accountId = selected?.account_id ?? (header && header.id === selectedId ? header.account_id : null);

  return (
    <div className="-mx-4 -mb-28 -mt-6 md:-mx-8 md:-mb-10 md:-mt-8">
      <div className="flex h-[calc(100dvh-7rem-env(safe-area-inset-bottom,0px))] md:h-[calc(100dvh-3.5rem)]">
        {/* Conversation list */}
        <aside className={cn("w-full shrink-0 flex-col border-r border-line bg-surface md:flex md:w-80", showThread ? "hidden" : "flex")} aria-label="Conversations">
          <div className="space-y-2 border-b border-line p-3">
            <div className="flex items-center justify-between gap-2">
              <h1 className="text-base font-semibold tracking-tight">Chat</h1>
              <button type="button" onClick={startNew} className={buttonClass("primary", "sm")}>
                <MessageSquarePlus className="h-4 w-4" aria-hidden="true" /> New chat
              </button>
            </div>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden="true" />
              <label htmlFor="chat-search" className="sr-only">Search conversations</label>
              <input id="chat-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search chats and accounts" className={cn(inputClass, "pl-8")} />
            </div>
          </div>
          <ul className="min-h-0 flex-1 overflow-y-auto">
            {filtered.map((c) => (
              <ThreadRow key={c.id} chat={c} active={c.id === selectedId} onOpen={() => open(c.id)} />
            ))}
            {filtered.length === 0 && (
              <li className="p-4 text-sm text-muted">{query ? `Nothing matches “${query}”.` : "No conversations yet. Start with New chat."}</li>
            )}
          </ul>
        </aside>

        {/* Conversation */}
        <section className={cn("min-w-0 flex-1 flex-col bg-canvas", showThread ? "flex" : "hidden md:flex")} aria-label={title}>
          <header className="flex items-center gap-2 border-b border-line bg-surface px-3 py-2.5">
            <button type="button" onClick={() => router.replace("/chat")} className="rounded-md p-1.5 text-muted hover:bg-subtle hover:text-ink md:hidden" aria-label="Back to conversations">
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            </button>
            <div className="min-w-0 flex-1">
              <h2 className={cn("truncate text-sm font-semibold", accountId && "font-mono")}>{title}</h2>
              {selected?.email && <p className="truncate text-xs text-muted">{selected.email}</p>}
            </div>
            {accountId && (
              <>
                <Link href={`/mailboxes?account=${accountId}`} className={buttonClass("ghost", "sm")}>
                  <Mail className="h-4 w-4" aria-hidden="true" /> <span className="hidden sm:inline">Mailbox</span>
                </Link>
                <Link href={`/accounts/${accountId}`} className={buttonClass("ghost", "sm")}>
                  <KeyRound className="h-4 w-4" aria-hidden="true" /> <span className="hidden sm:inline">Vault</span>
                </Link>
              </>
            )}
          </header>
          <div className="min-h-0 flex-1 p-3">
            {api ? (
              <Conversation key={selectedId ?? "new"} api={api} resetKey={selectedId ?? "new"} domain={accountId ? title : undefined} tall onActivity={onActivity} />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted">Pick a conversation or start a new chat.</div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <ChatInner />
    </Suspense>
  );
}
