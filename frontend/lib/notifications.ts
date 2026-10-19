"use client";

import { useSyncExternalStore } from "react";
import {
  AppNotification, listNotifications, markNotificationsRead, openNotificationStream,
  deleteNotification, clearNotifications, isAuthenticated,
} from "@/lib/api";

/**
 * One notification connection for the whole app (not one per component).
 * The server ends each stream after ~55s; we reconnect and resume from the last event id.
 */
interface State {
  items: AppNotification[];
  unread: number;
  connected: boolean;
  loaded: boolean;
}

let state: State = { items: [], unread: 0, connected: false, loaded: false };
const listeners = new Set<() => void>();
let started = false;
let abort: AbortController | null = null;
let lastId: number | null = null;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
const toastListeners = new Set<(n: AppNotification) => void>();

function set(next: Partial<State>) {
  state = { ...state, ...next };
  listeners.forEach((l) => l());
}

export function onNotificationToast(fn: (n: AppNotification) => void) {
  toastListeners.add(fn);
  return () => {
    toastListeners.delete(fn);
  };
}

function receive(n: AppNotification) {
  if (state.items.some((i) => i.id === n.id)) return;
  set({ items: [n, ...state.items].slice(0, 100), unread: state.unread + (n.read ? 0 : 1) });
  toastListeners.forEach((fn) => fn(n));
}

function parseFrames(buffer: string, onFrame: (event: string, data: string, id: string) => void): string {
  let rest = buffer;
  let idx: number;
  while ((idx = rest.indexOf("\n\n")) !== -1) {
    const raw = rest.slice(0, idx);
    rest = rest.slice(idx + 2);
    let event = "message";
    let id = "";
    const data: string[] = [];
    for (const line of raw.split("\n")) {
      if (line.startsWith(":")) continue;
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("id:")) id = line.slice(3).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (data.length) onFrame(event, data.join("\n"), id);
  }
  return rest;
}

async function connectOnce(signal: AbortSignal) {
  const res = await openNotificationStream(lastId, signal);
  if (!res.ok || !res.body) throw new Error(`stream ${res.status}`);
  set({ connected: true });
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer = parseFrames(buffer + decoder.decode(value, { stream: true }), (event, data, id) => {
      try {
        const parsed = JSON.parse(data);
        if (event === "ready") set({ unread: parsed.unread });
        else if (event === "unread") set({ unread: parsed.unread });
        else if (event === "notification") {
          receive(parsed as AppNotification);
          if (id) lastId = Number(id);
        }
      } catch {
        /* ignore a malformed frame */
      }
    });
  }
}

async function loop() {
  while (started) {
    abort = new AbortController();
    try {
      await connectOnce(abort.signal);
    } catch {
      /* fall through to the delay below */
    }
    set({ connected: false });
    if (!started) return;
    await new Promise<void>((resolve) => {
      retryTimer = setTimeout(resolve, 3000);
    });
  }
}

export async function refreshNotifications() {
  try {
    const data = await listNotifications();
    if (lastId === null && data.results.length) lastId = Math.max(...data.results.map((n) => n.id));
    set({ items: data.results, unread: data.unread, loaded: true });
  } catch {
    set({ loaded: true });
  }
}

export function startNotifications() {
  if (started || typeof window === "undefined" || !isAuthenticated()) return;
  started = true;
  void refreshNotifications().then(() => {
    if (started) void loop();
  });
}

export function stopNotifications() {
  started = false;
  abort?.abort();
  if (retryTimer) clearTimeout(retryTimer);
  lastId = null;
  state = { items: [], unread: 0, connected: false, loaded: false };
  listeners.forEach((l) => l());
}

export async function markRead(ids?: number[]) {
  const data = await markNotificationsRead(ids);
  set({
    unread: data.unread,
    items: state.items.map((n) => (!ids || ids.includes(n.id) ? { ...n, read: true } : n)),
  });
}

export async function removeNotification(id: number) {
  await deleteNotification(id);
  const gone = state.items.find((n) => n.id === id);
  set({ items: state.items.filter((n) => n.id !== id), unread: Math.max(0, state.unread - (gone && !gone.read ? 1 : 0)) });
}

export async function removeAllNotifications() {
  await clearNotifications();
  set({ items: [], unread: 0 });
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
};

export function useNotifications(): State {
  return useSyncExternalStore(subscribe, () => state, () => state);
}
