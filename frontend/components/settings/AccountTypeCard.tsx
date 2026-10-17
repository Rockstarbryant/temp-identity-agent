"use client";

import { useState } from "react";
import Link from "next/link";
import { Hourglass, Infinity as InfinityIcon, Loader2 } from "lucide-react";
import { AccountMode, ApiError, setAccountMode } from "@/lib/api";
import Section from "./Section";

interface Props {
  mode: AccountMode;
  emailConnected: boolean;
  onChange: (mode: AccountMode) => void;
}

const OPTIONS: { mode: AccountMode; title: string; text: string; icon: typeof Hourglass }[] = [
  {
    mode: "temporary",
    title: "Temporary",
    text: "A throwaway identity and a disposable inbox. Nothing links back to you. Expires automatically.",
    icon: Hourglass,
  },
  {
    mode: "permanent",
    title: "Permanent",
    text: "Uses your own email and saved details, so the account is really yours. Needs your email connected below.",
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
      setError(err instanceof ApiError ? String(err.message) : "Could not save. Try again.");
    } finally {
      setSaving(null);
    }
  }

  return (
    <Section title="Account type" hint="What the agent creates when you give it a site to register on.">
      <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Account type">
        {OPTIONS.map(({ mode: m, title, text, icon: Icon }) => {
          const selected = mode === m;
          return (
            <button
              key={m}
              role="radio"
              aria-checked={selected}
              onClick={() => choose(m)}
              className={`rounded-md border p-3 text-left transition ${
                selected ? "border-accent bg-accent/5 ring-1 ring-accent" : "border-black/15 hover:bg-black/[0.02]"
              }`}
            >
              <div className="flex items-center gap-2 text-sm font-medium">
                {saving === m ? <Loader2 className="h-4 w-4 animate-spin" /> : <Icon className="h-4 w-4" />}
                {title}
                {selected && <span className="ml-auto text-xs text-accent">Selected</span>}
              </div>
              <p className="mt-1 text-xs text-black/60">{text}</p>
            </button>
          );
        })}
      </div>
      {mode === "permanent" && !emailConnected && (
        <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Permanent accounts need your email so the agent can read verification codes and links. Connect it in the
          &ldquo;Your email&rdquo; section below. Until then new jobs won&apos;t start.
        </p>
      )}
      {error && <p className="mt-3 text-xs text-red-600">{error}</p>}
      <p className="mt-3 text-xs text-black/40">
        This applies to new jobs. Form filling (<Link href="/" className="underline">paste a Google Form on the home page</Link>)
        doesn&apos;t create an account, so it ignores this.
      </p>
    </Section>
  );
}
