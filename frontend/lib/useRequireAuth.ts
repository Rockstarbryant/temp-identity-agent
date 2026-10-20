"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/api";

/**
 * Redirects to /login (remembering where the user was) when there is no session.
 * Returns true once a session exists, so pages can hold their data fetches until then.
 * Token refresh itself stays in lib/api.ts; an expired refresh token is handled by the
 * first API call that returns 401.
 */
export function useRequireAuth(): boolean {
  const router = useRouter();
  const pathname = usePathname() || "/";
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      const here = pathname + (typeof window !== "undefined" ? window.location.search : "");
      router.replace(`/login?next=${encodeURIComponent(here)}`);
      return;
    }
    setReady(true);
  }, [pathname, router]);

  return ready;
}

/** `next` values must be same-site paths: never an absolute or protocol-relative URL. */
export function safeNextPath(raw: string | null, fallback = "/dashboard"): string {
  if (!raw) return fallback;
  if (!raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return fallback;
  return raw;
}
