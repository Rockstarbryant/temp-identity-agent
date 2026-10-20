import { Cpu } from "lucide-react";

const PROVIDER_NAMES: Record<string, string> = {
  openrouter: "OpenRouter",
  groq: "Groq",
};

/** Which AI provider and model handled (or is handling) the task, as reported by the backend. */
export default function AiBadge({ provider, model }: { provider: string; model: string }) {
  const name = PROVIDER_NAMES[provider] || provider;
  const text = provider ? `${name} · ${model || "model pending"}` : "Model not selected yet";
  return (
    <span
      title={text}
      className="inline-flex max-w-full items-center gap-1 rounded-md border border-line bg-subtle px-2 py-0.5 font-mono text-[11px] text-muted"
    >
      <Cpu className="h-3 w-3 shrink-0" aria-hidden="true" />
      <span className="truncate">{text}</span>
    </span>
  );
}
