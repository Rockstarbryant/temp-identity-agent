"use client";

import { ReactNode, useEffect, useRef } from "react";
import { cn } from "./cn";

interface Props {
  open: boolean;
  onClose: () => void;
  /** Id of the element that titles the overlay (for screen readers). */
  labelledBy: string;
  describedBy?: string;
  side?: "center" | "right";
  children: ReactNode;
}

/**
 * Accessible modal built on the native <dialog> element: focus is trapped, Escape closes it,
 * the page behind is inert, and focus returns to the trigger on close. The page does not
 * scroll while it is open. Children are only mounted while open.
 */
export default function Overlay({ open, onClose, labelledBy, describedBy, side = "center", children }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className={cn(
        "bg-surface p-0 text-ink backdrop:bg-black/50",
        side === "center"
          ? "w-[calc(100%-2rem)] max-w-md rounded-lg border border-line shadow-sm"
          : "fixed inset-y-0 left-auto right-0 m-0 h-full max-h-none w-full max-w-md border-l border-line",
      )}
    >
      {open ? children : null}
    </dialog>
  );
}
