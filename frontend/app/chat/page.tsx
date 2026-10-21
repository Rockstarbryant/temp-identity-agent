"use client";

import Link from "next/link";
import { Suspense, useCallback, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, KeyRound, Loader2, Mail, MessageSquare, Search } from "lucide-react";
import { ChatSummary, listChats } from "@/lib/api";
import { useCachedData } from "@/lib/useCachedData";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { timeAgo } from "@/lib/format";
import AccountChat from "@/components/vault/AccountChat";
import { buttonClass } from "@/components/ui/Button";
import { inputClass } from "@/components/ui/Field";
import { cn } from "@/components/ui/cn";
import { EmptyState, ErrorState, PageSpinner } from "@/components/ui/States";

const CACHE_KEY = "chats";

function ThreadRow({ chat, active, onOpen }: { chat: ChatSummary; active: boolean; onOpen: () => void }) {
  const last = chat.last_message;
  return (
    <li>
      <button
        type="button" onClick={onOpen} aria-current={active ? "true" : undefined}
        className={cn(
          "flex w-full items-start gap-3 border-b border-line px-3 py-3 text-left transition-colors",
          active ? "bg-accent-soft" : "hover:bg-subtle",
        )}
      >
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-subtle text-xs font-semibold uppercase text-muted" aria-hidden="true">
          {chat.domain.replace(/^(www|account|app)\./, "").charAt(0)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-2">
            <span className={cn("truncate font-mono text-sm", active ? "font-semibold text-accent-strong" : "font-medium text-ink")}>{chat.domain}</span>
            <span className="shrink-0 text-[11px] text-muted">{last ? timeAgo(last.created_at) : ""}</span>
          </span>
          <span className="mt-0.5 flex items-center gap-1.5 text-xs text-muted">
            {chat.working && <Loader2 className="h-3 w-3 shrink-0 animate-spin text-accent" aria-label="Working on the site" />}
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
  const { data, error, loading, refresh } = useCachedData(ready ? CACHE_KEY : null, async () => (await listChats()).results, { refreshMs: 15000 });

  const wanted = params.get("account");
  const chats = useMemo(() => data ?? [], [data]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? chats.filter((c) => c.domain.toLowerCase().includes(q) || c.email.toLowerCase().includes(q)) : chats;
  }, [chats, query]);
  const selected = chats.find((c) => c.account_id === wanted) ?? null;
  const onActivity = useCallback(() => void refresh(), [refresh]);

  if (!ready || (loading && !error)) return <PageSpinner />;
  if (error && !data) return <ErrorState title="Could not load your chats" message="Check your connection and try again." onRetry={() => void refresh()} />;
  if (chats.length === 0) {
    return (
      <EmptyState
        icon={<MessageSquare className="h-4 w-4" aria-hidden="true" />}
        title="No conversations yet"
        description="Every account in your Identity Vault gets its own conversation. Start a task and the account will appear here when it's done."
        action={<Link href="/new" className={buttonClass("primary")}>Start a task</Link>}
      />
    );
  }

  const open = (id: string) => router.replace(`/chat?account=${id}`);
  // Desktop opens the most recent conversation by default. On a phone the list is the landing view.
  const desktopSelected = selected ?? chats[0];

  return (
    <div className="-mx-4 -mb-28 -mt-6 md:-mx-8 md:-mb-10 md:-mt-8">
      <div className="flex h-[calc(100dvh-7rem-env(safe-area-inset-bottom,0px))] md:h-[calc(100dvh-3.5rem)]">
        {/* Conversation list */}
        <aside
          className={cn(
            "w-full shrink-0 flex-col border-r border-line bg-surface md:flex md:w-80",
            selected ? "hidden" : "flex",
          )}
          aria-label="Conversations"
        >
          <div className="border-b border-line p-3">
            <h1 className="mb-2 text-base font-semibold tracking-tight">Chat</h1>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden="true" />
              <label htmlFor="chat-search" className="sr-only">Search conversations</label>
              <input id="chat-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search accounts"
                     className={cn(inputClass, "pl-8")} />
            </div>
          </div>
          <ul className="min-h-0 flex-1 overflow-y-auto">
            {filtered.map((c) => (
              <ThreadRow key={c.account_id} chat={c} active={c.account_id === desktopSelected.account_id} onOpen={() => open(c.account_id)} />
            ))}
            {filtered.length === 0 && <li className="p-4 text-sm text-muted">No account matches “{query}”.</li>}
          </ul>
        </aside>

        {/* Conversation */}
        <section className={cn("min-w-0 flex-1 flex-col bg-canvas", selected ? "flex" : "hidden md:flex")} aria-label={`Conversation about ${desktopSelected.domain}`}>
          <header className="flex items-center gap-2 border-b border-line bg-surface px-3 py-2.5">
            <button type="button" onClick={() => router.replace("/chat")} className="rounded-md p-1.5 text-muted hover:bg-subtle hover:text-ink md:hidden" aria-label="Back to conversations">
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            </button>
            <div className="min-w-0 flex-1">
              <h2 className="truncate font-mono text-sm font-semibold">{desktopSelected.domain}</h2>
              <p className="truncate text-xs text-muted">{desktopSelected.email}</p>
            </div>
            <Link href={`/mailboxes?account=${desktopSelected.account_id}`} className={buttonClass("ghost", "sm")}>
              <Mail className="h-4 w-4" aria-hidden="true" /> <span className="hidden sm:inline">Mailbox</span>
            </Link>
            <Link href={`/accounts/${desktopSelected.account_id}`} className={buttonClass("ghost", "sm")}>
              <KeyRound className="h-4 w-4" aria-hidden="true" /> <span className="hidden sm:inline">Vault</span>
            </Link>
          </header>
          <div className="min-h-0 flex-1 p-3">
            <AccountChat key={desktopSelected.account_id} accountId={desktopSelected.account_id} domain={desktopSelected.domain} tall onActivity={onActivity} />
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
