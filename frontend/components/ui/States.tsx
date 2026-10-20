import { ReactNode } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import Button from "./Button";
import { cn } from "./cn";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("rounded-md bg-subtle motion-safe:animate-pulse", className)} />;
}

/** Placeholder rows shown while a list loads for the first time. */
export function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="divide-y divide-line rounded-lg border border-line bg-surface">
      <span className="sr-only">Loading</span>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 px-4 py-3.5">
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-3 w-56 max-w-full" />
          </div>
          <Skeleton className="h-5 w-20" />
        </div>
      ))}
    </div>
  );
}

export function PageSpinner({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex justify-center py-16 text-muted">
      <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </div>
  );
}

export function EmptyState({
  icon, title, description, action,
}: { icon?: ReactNode; title: string; description?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line-strong bg-surface px-6 py-10 text-center">
      {icon && <div className="mx-auto mb-3 flex h-9 w-9 items-center justify-center rounded-md bg-subtle text-muted">{icon}</div>}
      <p className="text-sm font-medium text-ink">{title}</p>
      {description && <p className="mx-auto mt-1 max-w-sm text-sm text-muted">{description}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong", message, onRetry,
}: { title?: string; message?: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-danger-line bg-danger-soft px-4 py-4 text-sm">
      <p className="flex items-center gap-2 font-medium text-danger">
        <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" /> {title}
      </p>
      {message && <p className="mt-1 break-words text-ink/80">{message}</p>}
      {onRetry && (
        <Button size="sm" className="mt-3" onClick={onRetry}>Try again</Button>
      )}
    </div>
  );
}

/** Inline, dismiss-less message used inside forms and cards. */
export function InlineMessage({
  tone, children,
}: { tone: "danger" | "warning" | "success" | "info"; children: ReactNode }) {
  const styles = {
    danger: "border-danger-line bg-danger-soft text-danger",
    warning: "border-warning-line bg-warning-soft text-warning",
    success: "border-success-line bg-success-soft text-success",
    info: "border-line bg-subtle text-ink",
  }[tone];
  return (
    <p role={tone === "danger" ? "alert" : "status"} className={cn("break-words rounded-md border px-3 py-2 text-xs", styles)}>
      {children}
    </p>
  );
}
