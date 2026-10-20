"use client";

import { InputHTMLAttributes, ReactNode, forwardRef, useId } from "react";
import { cn } from "./cn";

export const inputClass =
  "w-full min-w-0 rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink " +
  "placeholder:text-muted/80 disabled:cursor-not-allowed disabled:bg-subtle disabled:text-muted " +
  "aria-[invalid=true]:border-danger";

interface FieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "className"> {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  mono?: boolean;
  className?: string;
  /** Visually hide the label (it is still read by screen readers). */
  hideLabel?: boolean;
  trailing?: ReactNode;
}

/** A labelled input with optional hint and error, wired up with aria-describedby. */
const Field = forwardRef<HTMLInputElement, FieldProps>(function Field(
  { label, hint, error, mono, className, hideLabel, trailing, id, ...rest },
  ref,
) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hintId = `${inputId}-hint`;
  const errId = `${inputId}-err`;
  const describedBy = [hint ? hintId : null, error ? errId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={className}>
      <label htmlFor={inputId} className={cn("mb-1 block text-xs font-medium text-ink", hideLabel && "sr-only")}>
        {label}
      </label>
      <div className="relative">
        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cn(inputClass, mono && "font-mono", trailing ? "pr-10" : "")}
          {...rest}
        />
        {trailing && <div className="absolute inset-y-0 right-1 flex items-center">{trailing}</div>}
      </div>
      {hint && <p id={hintId} className="mt-1 text-xs text-muted">{hint}</p>}
      {error && <p id={errId} role="alert" className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  );
});

export default Field;
