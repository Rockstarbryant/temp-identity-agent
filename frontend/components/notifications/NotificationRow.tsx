"use client";

import Link from "next/link";
import {
  AlertTriangle, Bell, CheckCircle2, Clock, KeyRound, Mail, Play, Plug, X, XCircle, Zap,
} from "lucide-react";
import { AppNotification, NotificationKind } from "@/lib/api";
import { markRead, removeNotification } from "@/lib/notifications";
import { timeAgo } from "@/lib/format";
import { cn } from "@/components/ui/cn";

const ICONS: Record<NotificationKind, { icon: typeof Bell; tone: string }> = {
  job_started: { icon: Play, tone: "text-accent-strong" },
  job_completed: { icon: CheckCircle2, tone: "text-success" },
  job_failed: { icon: XCircle, tone: "text-danger" },
  job_cancelled: { icon: X, tone: "text-muted" },
  job_needs_you: { icon: AlertTriangle, tone: "text-warning" },
  job_question: { icon: AlertTriangle, tone: "text-warning" },
  mail_received: { icon: Mail, tone: "text-accent-strong" },
  account_expiring: { icon: Clock, tone: "text-warning" },
  account_expired: { icon: Clock, tone: "text-muted" },
  signin_issue: { icon: AlertTriangle, tone: "text-danger" },
  client_connected: { icon: Plug, tone: "text-accent-strong" },
  manual_saved: { icon: KeyRound, tone: "text-success" },
  playbook_used: { icon: Zap, tone: "text-accent-strong" },
};

/**
 * New-mail notifications point at the account page; the Mailboxes workspace is the better
 * destination for them. Every other link is used exactly as the backend sent it.
 */
export function notificationHref(n: AppNotification): string {
  const m = n.kind === "mail_received" ? /^\/accounts\/([^/?#]+)\/?$/.exec(n.link) : null;
  return m ? `/mailboxes?account=${m[1]}` : n.link;
}

/** Only same-site paths are ever turned into links. */
function isInternalPath(href: string): boolean {
  return href.startsWith("/") && !href.startsWith("//");
}

export default function NotificationRow({
  n, onNavigate,
}: { n: AppNotification; onNavigate?: () => void }) {
  const { icon: Icon, tone } = ICONS[n.kind] ?? { icon: Bell, tone: "text-muted" };
  const href = n.link ? notificationHref(n) : "";

  const content = (
    <>
      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", tone)} aria-hidden="true" />
      <span className="min-w-0 flex-1">
        <span className={cn("block break-words text-sm", n.read ? "text-ink/80" : "font-medium text-ink")}>
          {!n.read && <span className="sr-only">Unread: </span>}
          {n.title}
        </span>
        {n.body && <span className="mt-0.5 block break-words text-xs text-muted">{n.body}</span>}
        <span className="mt-1 block text-[11px] text-muted">{timeAgo(n.created_at)}</span>
      </span>
    </>
  );

  return (
    <li
      className={cn(
        "flex items-start gap-1 rounded-lg border",
        n.read ? "border-line bg-surface" : "border-accent/30 bg-accent-soft",
      )}
    >
      {href && isInternalPath(href) ? (
        <Link
          href={href}
          onClick={() => {
            if (!n.read) void markRead([n.id]).catch(() => undefined);
            onNavigate?.();
          }}
          className="flex min-w-0 flex-1 items-start gap-3 rounded-lg px-3 py-2.5 hover:bg-black/[0.02]"
        >
          {content}
        </Link>
      ) : (
        <div className="flex min-w-0 flex-1 items-start gap-3 px-3 py-2.5">
          {content}
          {!n.read && (
            <button
              type="button"
              onClick={() => void markRead([n.id]).catch(() => undefined)}
              className="shrink-0 rounded px-1.5 py-0.5 text-xs text-accent-strong hover:underline"
            >
              Mark read
            </button>
          )}
        </div>
      )}
      <button
        type="button"
        onClick={() => void removeNotification(n.id).catch(() => undefined)}
        aria-label={`Dismiss notification: ${n.title}`}
        className="m-1.5 shrink-0 rounded p-1.5 text-muted hover:bg-subtle hover:text-danger"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </li>
  );
}
