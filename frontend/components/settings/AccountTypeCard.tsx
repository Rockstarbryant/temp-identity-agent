"use client";

import { useState } from "react";
import Link from "next/link";
import { Hourglass, Infinity as InfinityIcon, Loader2 } from "lucide-react";
import { AccountMode, ApiError, setAccountMode } from "@/lib/api";
import { InlineMessage } from "@/components/ui/States";
import { cn } from "@/components/ui/cn";
import Section from "./Section";

interface Props {
  mode: AccountMode;
  emailConnected: boolean;
  onChange: (mode: AccountMode) => void;
}

const OPTIONS: { mode: AccountMode; title: string; text: string; icon: typeof Hourglass }[] = [
  {
    mode: "temporary",
    title: "Temporary identity",
    text: "A throwaway name and a disposable inbox. Nothing links back to you, and the account expires automatically.",
    icon: Hourglass,
  },
  {
    mode: "permanent",
    title: "Permanent identity",
    text: "Uses your own email and saved details, so the account really belongs to you. Needs your email connected.",
    icon: InfinityIcon,
  },
];

export default function AccountTypeCard({ mode, emailConnected, onChange }: Props) {
  const [saving, setSaving] = useState<AccountMode | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function choose(next: AccountMode) {
    if (next === mode || saving) return;
    setSaving(next);
    setError(null);
    try {
      await setAccountMode(next);
      onChange(next);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.message) : "Could not save. Nothing was changed.");
    } finally {
      setSaving(null);
    }
  }

  return (
    <Section title="Identity type" hint="What the agent creates when you give it a site to register on. This is your default for every new task.">
      <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Identity type">
        {OPTIONS.map(({ mode: m, title, text, icon: Icon }) => {
          const selected = mode === m;
          return (
            <button
              key={m}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={saving !== null}
              onClick={() => void choose(m)}
              className={cn(
                "rounded-md border p-3 text-left transition-colors disabled:cursor-not-allowed",
                selected ? "border-accent bg-accent-soft" : "border-line-strong hover:bg-subtle",
              )}
            >
              <span className="flex items-center gap-2 text-sm font-medium">
                {saving === m ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Icon className="h-4 w-4" aria-hidden="true" />}
                {title}
                {selected && <span className="ml-auto text-xs font-normal text-accent-strong">Selected</span>}
              </span>
              <span className="mt-1 block text-xs text-muted">{text}</span>
            </button>
          );
        })}
      </div>
      {mode === "permanent" && !emailConnected && (
        <div className="mt-3">
          <InlineMessage tone="warning">
            Permanent identities need your email so the agent can read verification codes and links. Connect it in the Email tab. Until then new tasks will not start.
          </InlineMessage>
        </div>
      )}
      {error && <div className="mt-3"><InlineMessage tone="danger">{error}</InlineMessage></div>}
      <p className="mt-3 text-xs text-muted">
        This applies to new registration tasks. Filling in a form (<Link href="/new" className="text-accent-strong underline">paste a Google Form on Home</Link>)
        does not create an account, so it ignores this setting.
      </p>
    </Section>
  );
}
