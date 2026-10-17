// Tiny in-memory stale-while-revalidate cache shared by every page.
//
// Navigating between tabs used to remount each page with empty state, so every
// switch started with a spinner. Pages now render the last known data at once
// and refresh it in the background. The cache lives only in the browser tab.

const store = new Map<string, unknown>();

export function getCached<T>(key: string | null): T | undefined {
  if (!key || typeof window === "undefined") return undefined;
  return store.get(key) as T | undefined;
}

export function setCached<T>(key: string, value: T): void {
  if (typeof window === "undefined") return;
  store.set(key, value);
}

export function invalidate(prefix?: string): void {
  if (!prefix) {
    store.clear();
    return;
  }
  Array.from(store.keys()).forEach((k) => {
    if (k.startsWith(prefix)) store.delete(k);
  });
}

export function clearCache(): void {
  store.clear();
}
