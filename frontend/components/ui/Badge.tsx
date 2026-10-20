import { ReactNode } from "react";
import { cn } from "./cn";

export type BadgeTone = "neutral" | "info" | "success" | "warning" | "danger" | "accent";

const TONES: Record<BadgeTone, string> = {
  neutral: "border-line bg-subtle text-muted",
  info: "border-line bg-surface text-ink",
  success: "border-success-line bg-success-soft text-success",
  warning: "border-warning-line bg-warning-soft text-warning",
  danger: "border-danger-line bg-danger-soft text-danger",
  accent: "border-accent/30 bg-accent-soft text-accent-strong",
};

/** Small status label. Always contains text (and usually an icon): colour is never the only signal. */
export default function Badge({
  tone = "neutral", icon, children, className,
}: { tone?: BadgeTone; icon?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1 whitespace-nowrap rounded-md border px-2 py-0.5 text-xs font-medium",
        TONES[tone], className,
      )}
    >
      {icon}
      <span className="truncate">{children}</span>
    </span>
  );
}
