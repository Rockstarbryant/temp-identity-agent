"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Copy } from "lucide-react";
import { useToast } from "./Feedback";
import { cn } from "./cn";

/**
 * Copies `value` to the clipboard. Nothing is logged and the value never leaves the browser.
 * `label` names what is copied ("password", "verification code") for screen readers.
 */
export default function CopyButton({
  value, label, className, withText = false,
}: { value: string; label: string; className?: string; withText?: boolean }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const toast = useToast();

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error(`Could not copy the ${label}. Your browser blocked clipboard access.`);
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      aria-label={`Copy ${label}`}
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-md p-1.5 text-muted transition-colors hover:bg-subtle hover:text-ink",
        withText && "px-2 text-xs",
        className,
      )}
    >
      {copied ? <Check className="h-4 w-4 text-success" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
      {withText && <span>{copied ? "Copied" : "Copy"}</span>}
      <span role="status" className="sr-only">{copied ? `${label} copied` : ""}</span>
    </button>
  );
}
