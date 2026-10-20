"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { isAuthenticated } from "@/lib/api";

/**
 * A call-to-action that works without JavaScript (visitors go to sign-up) and, once the page
 * has loaded, sends people who are already logged in straight to the workspace instead.
 */
export default function AuthCta({
  className, guestLabel, authedLabel = "Open app", guestHref = "/register", authedHref = "/new", children,
}: {
  className: string;
  guestLabel: string;
  authedLabel?: string;
  guestHref?: string;
  authedHref?: string;
  children?: ReactNode;
}) {
  const [authed, setAuthed] = useState(false);
  useEffect(() => {
    setAuthed(isAuthenticated());
  }, []);
  return (
    <Link href={authed ? authedHref : guestHref} className={className}>
      {authed ? authedLabel : guestLabel}
      {children}
    </Link>
  );
}
