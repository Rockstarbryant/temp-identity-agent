"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Bell } from "lucide-react";
import { startNotifications, useNotifications } from "@/lib/notifications";

export default function NotificationBell() {
  const { unread, connected } = useNotifications();

  useEffect(() => {
    startNotifications();
  }, []);

  // Show the count in the browser tab too, so a background tab still tells you something happened.
  useEffect(() => {
    const base = document.title.replace(/^\(\d+\)\s*/, "");
    document.title = unread > 0 ? `(${unread}) ${base}` : base;
  }, [unread]);

  return (
    <Link
      href="/notifications"
      className="relative rounded-md p-2 text-black/60 hover:bg-black/5 hover:text-ink"
      aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
    >
      <Bell className="h-5 w-5" />
      {unread > 0 && (
        <span className="absolute right-0.5 top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold leading-none text-white">
          {unread > 99 ? "99+" : unread}
        </span>
      )}
      <span
        className={`absolute bottom-1 right-1 h-1.5 w-1.5 rounded-full ${connected ? "bg-green-500" : "bg-black/20"}`}
        title={connected ? "Live" : "Reconnecting…"}
      />
    </Link>
  );
}
