"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { Bell, X } from "lucide-react";
import { markRead, startNotifications, useNotifications } from "@/lib/notifications";
import Overlay from "@/components/ui/Overlay";
import Button, { buttonClass } from "@/components/ui/Button";
import NotificationRow from "@/components/notifications/NotificationRow";

const DRAWER_LIMIT = 15;

/**
 * Header bell and slide-over drawer. It reads the single app-wide notification store in
 * lib/notifications.ts (one stream, started once), so opening the drawer never opens a
 * second connection or triggers an extra fetch.
 */
export default function NotificationBell() {
  const { items, unread, loaded, connected } = useNotifications();
  const [open, setOpen] = useState(false);
  const titleId = useId();

  useEffect(() => {
    startNotifications();
  }, []);

  // Keep the unread count in the browser tab title so a background tab still shows it.
  useEffect(() => {
    const base = document.title.replace(/^\(\d+\)\s*/, "");
    document.title = unread > 0 ? `(${unread}) ${base}` : base;
  }, [unread]);

  const recent = items.slice(0, DRAWER_LIMIT);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
        className="relative inline-flex h-9 w-9 items-center justify-center rounded-md text-muted transition-colors hover:bg-subtle hover:text-ink"
      >
        <Bell className="h-[18px] w-[18px]" aria-hidden="true" />
        {unread > 0 && (
          <span className="tabular absolute right-0 top-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent-strong px-1 text-[10px] font-semibold leading-none text-white">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      <Overlay open={open} onClose={() => setOpen(false)} labelledBy={titleId} side="right">
        <div className="flex h-full flex-col">
          <header className="flex items-center justify-between gap-2 border-b border-line px-4 py-3">
            <div>
              <h2 id={titleId} className="text-sm font-semibold">Notifications</h2>
              <p className="text-xs text-muted">{connected ? "Receiving updates" : "Reconnecting to updates"}</p>
            </div>
            <div className="flex items-center gap-1">
              {unread > 0 && (
                <Button size="sm" variant="ghost" onClick={() => void markRead().catch(() => undefined)}>
                  Mark all read
                </Button>
              )}
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close notifications"
                className="rounded-md p-2 text-muted hover:bg-subtle hover:text-ink"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {!loaded ? (
              <p role="status" className="py-8 text-center text-sm text-muted">Loading</p>
            ) : recent.length === 0 ? (
              <p className="rounded-lg border border-dashed border-line-strong px-4 py-8 text-center text-sm text-muted">
                No notifications yet. Finished tasks, new mail and anything that needs you will appear here.
              </p>
            ) : (
              <ul className="space-y-2">
                {recent.map((n) => (
                  <NotificationRow key={n.id} n={n} onNavigate={() => setOpen(false)} />
                ))}
              </ul>
            )}
          </div>

          <footer className="border-t border-line p-3">
            <Link
              href="/notifications"
              onClick={() => setOpen(false)}
              className={buttonClass("secondary", "md", "w-full")}
            >
              View all notifications
            </Link>
          </footer>
        </div>
      </Overlay>
    </>
  );
}
