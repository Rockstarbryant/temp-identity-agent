"use client";

import { useEffect } from "react";

/** Registers the service worker in production builds only (it would get in the way of dev hot reload). */
export default function PwaRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
      /* Not installable on this browser; the site works normally without it. */
    });
  }, []);
  return null;
}
