import { ReactNode, useId } from "react";

/** A titled settings card. */
export default function Section({ title, hint, children }: { title: string; hint?: ReactNode; children: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="rounded-lg border border-line bg-surface">
      <header className="border-b border-line px-4 py-3">
        <h2 id={id} className="text-sm font-semibold">{title}</h2>
        {hint && <p className="mt-0.5 max-w-prose text-xs text-muted">{hint}</p>}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}
