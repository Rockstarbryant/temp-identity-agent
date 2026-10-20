/**
 * Helpers for starting a task from a link instead of the Home form.
 *
 * Supported shapes:
 *   <site>/@direct/https://example.com        (typed or bookmarked)
 *   <site>/@direct/https%3A%2F%2Fexample.com  (fully encoded)
 *   <site>/direct?url=https://example.com     (also used by the PWA share target)
 *   "@direct https://example.com" typed into the Home field
 *
 * Opening such a link never starts a task by itself: the /direct page shows what it found and
 * waits for one explicit confirmation, so a link someone sends you cannot spend your tasks.
 */

const SCHEME = /^[a-z][a-z0-9+.-]*:\/\//i;

/** Accepts "example.com/signup" as well as full URLs. Returns null unless it is a plain http(s) address. */
export function normalizeUrl(raw: string): string | null {
  const text = raw.trim();
  if (!text) return null;
  const withScheme = SCHEME.test(text) ? text : `https://${text}`;
  try {
    const u = new URL(withScheme);
    if (u.protocol !== "https:" && u.protocol !== "http:") return null;
    if (u.username || u.password) return null; // never accept credentials embedded in a link
    if (!u.hostname.includes(".") && u.hostname !== "localhost") return null;
    return u.toString();
  } catch {
    return null;
  }
}

export function isGoogleForm(raw: string): boolean {
  try {
    const u = new URL(raw);
    return (u.hostname === "docs.google.com" && u.pathname.startsWith("/forms")) || u.hostname === "forms.gle";
  } catch {
    return false;
  }
}

/** Removes a leading "@direct" (and following space, colon or slash) from typed text. */
export function stripDirectPrefix(text: string): string {
  return text.replace(/^\s*@direct[\s:/]*/i, "");
}

function safeDecode(s: string): string {
  if (!s.includes("%")) return s;
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}

/** First http(s) URL inside shared text, for share targets that put the link in "text". */
function firstUrlIn(text: string): string | null {
  const m = /https?:\/\/[^\s<>"']+/i.exec(text);
  return m ? m[0] : null;
}

/**
 * Works out the target address from the /direct route.
 * Browsers and proxies often collapse "https://" in a path to "https:/", which is repaired here.
 */
export function extractDirectTarget(opts: { segments?: string[]; search: string; hash: string }): string | null {
  const q = new URLSearchParams(opts.search);
  const fromQuery = q.get("url") || (q.get("text") ? firstUrlIn(q.get("text") as string) : null);
  if (fromQuery) return normalizeUrl(stripDirectPrefix(fromQuery));

  const segs = (opts.segments ?? []).map(safeDecode).filter((s) => s.length > 0);
  if (segs.length === 0) return null;

  let joined: string;
  if (/^https?:$/i.test(segs[0])) joined = `${segs[0]}//${segs.slice(1).join("/")}`;
  else joined = segs.join("/");

  // A query string or fragment on the target belongs to the target.
  const tail = `${opts.search}${opts.hash}`;
  return normalizeUrl(stripDirectPrefix(joined + tail));
}
