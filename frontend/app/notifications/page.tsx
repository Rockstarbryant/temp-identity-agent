"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle, Bell, CheckCircle2, Clock, KeyRound, Mail, Play, Plug, Trash2, X, XCircle, Zap,
} from "lucide-react";
import { AppNotification, NotificationKind, isAuthenticated } from "@/lib/api";
import {
  markRead, refreshNotifications, removeAllNotifications, removeNotification,
  startNotifications, useNotifications,
} from "@/lib/notifications";

const ICONS: Record<NotificationKind, { icon: typeof Bell; tone: string }> = {
  job_started: { icon: Play, tone: "text-blue-600" },
  job_completed: { icon: CheckCircle2, tone: "text-green-600" },
  job_failed: { icon: XCircle, tone: "text-red-600" },
  job_cancelled: { icon: X, tone: "text-black/50" },
  job_needs_you: { icon: AlertTriangle, tone: "text-amber-600" },
  job_question: { icon: AlertTriangle, tone: "text-amber-600" },
  mail_received: { icon: Mail, tone: "text-accent" },
  account_expiring: { icon: Clock, tone: "text-amber-600" },
  account_expired: { icon: Clock, tone: "text-black/50" },
  signin_issue: { icon: AlertTriangle, tone: "text-red-600" },
  client_connected: { icon: Plug, tone: "text-accent" },
  manual_saved: { icon: KeyRound, tone: "text-green-600" },
  playbook_used: { icon: Zap, tone: "text-accent" },
};

function ago(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

function Row({ n }: { n: AppNotification }) {
  const { icon: Icon, tone } = ICONS[n.kind] ?? { icon: Bell, tone: "text-black/50" };
  const body = (
    <div className="flex min-w-0 flex-1 items-start gap-3">
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${tone}`} />
      <div className="min-w-0">
        <p className={`break-words text-sm ${n.read ? "text-black/70" : "font-medium text-ink"}`}>{n.title}</p>
        {n.body && <p className="mt-0.5 break-words text-xs text-black/50">{n.body}</p>}
        <p className="mt-1 text-[11px] text-black/40">{ago(n.created_at)}</p>
      </div>
    </div>
  );
  return (
    <li className={`flex items-start gap-2 rounded-md border px-3 py-2.5 ${n.read ? "border-black/10 bg-white" : "border-accent/30 bg-accent/5"}`}>
      {n.link ? (
        <Link href={n.link} onClick={() => !n.read && markRead([n.id])} className="flex min-w-0 flex-1">
          {body}
        </Link>
      ) : (
        body
      )}
      <button onClick={() => removeNotification(n.id)} className="rounded p-1 text-black/30 hover:bg-black/5 hover:text-red-600" aria-label="Dismiss">
        <X className="h-4 w-4" />
      </button>
    </li>
  );
}

export default function NotificationsPage() {
  const { items, unread, loaded, connected } = useNotifications();
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login?next=/notifications");
      return;
    }
    startNotifications();
    void refreshNotifications();
  }, [router]);

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">Notifications</h1>
          <p className="text-xs text-black/40">{connected ? "Live: new events appear here as they happen." : "Reconnecting…"}</p>
        </div>
        <div className="flex items-center gap-3 text-sm">
          {unread > 0 && (
            <button onClick={() => markRead()} className="text-accent hover:underline">Mark all read</button>
          )}
          {items.length > 0 && (
            <button onClick={() => confirm("Clear all notifications?") && removeAllNotifications()} className="flex items-center gap-1 text-black/50 hover:text-red-600">
              <Trash2 className="h-4 w-4" /> Clear
            </button>
          )}
        </div>
      </div>

      {loaded && items.length === 0 && (
        <p className="rounded-md border border-dashed border-black/15 p-6 text-center text-sm text-black/40">
          Nothing yet. You&apos;ll see new mail in your vault mailboxes, finished jobs and anything that needs you here.
        </p>
      )}
      <ul className="space-y-2">
        {items.map((n) => <Row key={n.id} n={n} />)}
      </ul>
    </div>
  );
}
