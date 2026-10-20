"use client";

import {
  ReactNode, createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState,
} from "react";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import Button from "./Button";
import Overlay from "./Overlay";
import { cn } from "./cn";

type ToastTone = "success" | "error" | "info";
interface ToastItem { id: number; tone: ToastTone; message: string }

export interface ConfirmOptions {
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Destructive actions get a red confirm button. */
  destructive?: boolean;
}

interface Ctx {
  toast: (tone: ToastTone, message: string) => void;
  confirm: (options: ConfirmOptions) => Promise<boolean>;
}

const FeedbackContext = createContext<Ctx | null>(null);

export function useToast() {
  const ctx = useContext(FeedbackContext);
  if (!ctx) throw new Error("useToast must be used inside FeedbackProvider");
  return useMemo(
    () => ({
      success: (m: string) => ctx.toast("success", m),
      error: (m: string) => ctx.toast("error", m),
      info: (m: string) => ctx.toast("info", m),
    }),
    [ctx],
  );
}

export function useConfirm() {
  const ctx = useContext(FeedbackContext);
  if (!ctx) throw new Error("useConfirm must be used inside FeedbackProvider");
  return ctx.confirm;
}

const TOAST_STYLES: Record<ToastTone, { box: string; icon: ReactNode }> = {
  success: { box: "border-success-line", icon: <CheckCircle2 className="h-4 w-4 text-success" aria-hidden="true" /> },
  error: { box: "border-danger-line", icon: <AlertCircle className="h-4 w-4 text-danger" aria-hidden="true" /> },
  info: { box: "border-line-strong", icon: <Info className="h-4 w-4 text-muted" aria-hidden="true" /> },
};

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [pending, setPending] = useState<{ options: ConfirmOptions; resolve: (ok: boolean) => void } | null>(null);
  const nextId = useRef(1);
  const titleId = useId();
  const descId = useId();

  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  const toast = useCallback(
    (tone: ToastTone, message: string) => {
      const id = nextId.current++;
      setToasts((t) => [...t.slice(-3), { id, tone, message }]);
      setTimeout(() => dismiss(id), tone === "error" ? 8000 : 4500);
    },
    [dismiss],
  );

  const confirm = useCallback(
    (options: ConfirmOptions) => new Promise<boolean>((resolve) => setPending({ options, resolve })),
    [],
  );

  const settle = useCallback(
    (ok: boolean) => {
      setPending((p) => {
        p?.resolve(ok);
        return null;
      });
    },
    [],
  );

  // Never leave a confirm() promise hanging if the provider unmounts.
  const pendingRef = useRef(pending);
  pendingRef.current = pending;
  useEffect(() => () => pendingRef.current?.resolve(false), []);

  const value = useMemo(() => ({ toast, confirm }), [toast, confirm]);

  return (
    <FeedbackContext.Provider value={value}>
      {children}

      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4 md:bottom-6"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role={t.tone === "error" ? "alert" : "status"}
            className={cn(
              "pointer-events-auto flex w-full max-w-sm items-start gap-2.5 rounded-lg border bg-surface px-3.5 py-3 text-sm shadow-sm",
              TOAST_STYLES[t.tone].box,
            )}
          >
            <span className="mt-0.5 shrink-0">{TOAST_STYLES[t.tone].icon}</span>
            <p className="min-w-0 flex-1 break-words">{t.message}</p>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss message"
              className="-m-1 rounded p-1 text-muted hover:bg-subtle hover:text-ink"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        ))}
      </div>

      <Overlay open={pending !== null} onClose={() => settle(false)} labelledBy={titleId} describedBy={descId}>
        {pending && (
          <div className="p-5">
            <h2 id={titleId} className="text-base font-semibold">{pending.options.title}</h2>
            {pending.options.description && (
              <div id={descId} className="mt-2 text-sm text-muted">{pending.options.description}</div>
            )}
            <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button onClick={() => settle(false)}>{pending.options.cancelLabel ?? "Cancel"}</Button>
              <Button variant={pending.options.destructive ? "danger" : "primary"} onClick={() => settle(true)} autoFocus>
                {pending.options.confirmLabel ?? "Confirm"}
              </Button>
            </div>
          </div>
        )}
      </Overlay>
    </FeedbackContext.Provider>
  );
}
