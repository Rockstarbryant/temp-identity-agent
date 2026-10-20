"use client";

import { Bell, Trash2 } from "lucide-react";
import { useEffect } from "react";
import { markRead, refreshNotifications, removeAllNotifications, startNotifications, useNotifications } from "@/lib/notifications";
import { useRequireAuth } from "@/lib/useRequireAuth";
import NotificationRow from "@/components/notifications/NotificationRow";
import Button from "@/components/ui/Button";
import PageHeader from "@/components/ui/PageHeader";
import { EmptyState, PageSpinner } from "@/components/ui/States";
import { useConfirm, useToast } from "@/components/ui/Feedback";

/** Full history. Uses the same single notification store and stream as the header drawer. */
export default function NotificationsPage() {
  const ready = useRequireAuth();
  const { items, unread, loaded, connected } = useNotifications();
  const confirm = useConfirm();
  const toast = useToast();

  useEffect(() => {
    if (!ready) return;
    startNotifications(); // no-op if the header bell already started it
    void refreshNotifications();
  }, [ready]);

  async function clearAll() {
    const ok = await confirm({
      title: "Clear all notifications?",
      description: "This deletes your notification history. It does not affect your tasks or accounts.",
      confirmLabel: "Clear all",
      destructive: true,
    });
    if (!ok) return;
    try {
      await removeAllNotifications();
    } catch {
      toast.error("Could not clear notifications.");
    }
  }

  if (!ready) return <PageSpinner />;

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="Notifications"
        description={connected ? "Receiving updates as they happen." : "Reconnecting to updates."}
        actions={
          <>
            {unread > 0 && <Button onClick={() => void markRead().catch(() => toast.error("Could not mark as read."))}>Mark all read</Button>}
            {items.length > 0 && (
              <Button variant="danger-ghost" onClick={clearAll}><Trash2 className="h-4 w-4" aria-hidden="true" /> Clear all</Button>
            )}
          </>
        }
      />
      {!loaded ? (
        <PageSpinner />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Bell className="h-4 w-4" aria-hidden="true" />}
          title="No notifications"
          description="Finished tasks, new mail in your mailboxes and anything that needs you will show up here."
        />
      ) : (
        <ul className="space-y-2">{items.map((n) => <NotificationRow key={n.id} n={n} />)}</ul>
      )}
    </div>
  );
}
