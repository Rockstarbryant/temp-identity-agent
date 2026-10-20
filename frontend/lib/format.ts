/** Small, dependency-free formatting helpers shared across pages. */

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString([], { dateStyle: "medium" });
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
}

/** "just now", "5 min ago", "3 h ago", then a plain date. */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)} d ago`;
  return formatDate(iso);
}

/** Host name of a link, for showing where a verification link goes without printing the whole token. */
export function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return "";
  }
}

/** Only http(s) links are ever rendered as clickable anchors. */
export function isSafeHttpUrl(url: string): boolean {
  try {
    const u = new URL(url);
    return u.protocol === "https:" || u.protocol === "http:";
  } catch {
    return false;
  }
}

export interface ExpiryInfo {
  label: string;
  /** "none" = permanent, "active" = still valid, "expired" = date passed. */
  tone: "none" | "active" | "expired";
}

/** Human description of when a vault account stops being usable. */
export function describeExpiry(account: { permanent: boolean; expires_at: string; status: string }): ExpiryInfo {
  if (account.permanent) return { label: "Permanent identity, no expiry", tone: "none" };
  const when = new Date(account.expires_at);
  if (Number.isNaN(when.getTime())) return { label: "Expiry unknown", tone: "active" };
  const ms = when.getTime() - Date.now();
  if (account.status === "expired" || ms <= 0) return { label: `Expired ${formatDate(account.expires_at)}`, tone: "expired" };
  const days = Math.floor(ms / 86400000);
  const hours = Math.floor(ms / 3600000);
  const rel = days >= 1 ? `in ${days} day${days === 1 ? "" : "s"}` : hours >= 1 ? `in ${hours} h` : "within the hour";
  return { label: `Expires ${formatDate(account.expires_at)} (${rel})`, tone: "active" };
}
