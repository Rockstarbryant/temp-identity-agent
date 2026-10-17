import { ReactNode } from "react";

export default function Section({ title, hint, children }: { title: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-sm font-semibold">{title}</h2>
        {hint && <p className="mt-0.5 text-xs text-black/50">{hint}</p>}
      </div>
      <div className="rounded-md border border-black/10 bg-white p-4">{children}</div>
    </section>
  );
}
