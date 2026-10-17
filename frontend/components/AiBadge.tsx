import { Cpu } from "lucide-react";

const PROVIDER_NAMES: Record<string, string> = {
  openrouter: "OpenRouter",
  groq: "Groq",
};

/** Shows which AI provider and model did (or is doing) the job. Always rendered. */
export default function AiBadge({ provider, model }: { provider: string; model: string }) {
  const name = PROVIDER_NAMES[provider] || provider;
  const text = provider ? `${name} · ${model || "model pending"}` : "AI model not selected yet";
  return (
    <span
      title={text}
      className="inline-flex max-w-full items-center gap-1 rounded-md bg-black/[0.04] px-2 py-0.5 text-xs text-black/60"
    >
      <Cpu className="h-3 w-3 shrink-0" />
      <span className="truncate">{text}</span>
    </span>
  );
}
