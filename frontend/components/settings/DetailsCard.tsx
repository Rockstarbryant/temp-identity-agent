"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, Plus, Trash2 } from "lucide-react";
import { ApiError, ProfileData, ProfileEntry, deleteProfileEntry, saveProfileEntry } from "@/lib/api";
import Section from "./Section";

interface Props {
  profile: ProfileData;
  onChange: (entries: ProfileEntry[]) => void;
}

function normalizeKey(raw: string) {
  return raw.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 60);
}

export default function DetailsCard({ profile, onChange }: Props) {
  const byKey = new Map(profile.entries.map((e) => [e.key, e]));
  const standardKeys = new Set(profile.standard_fields.map((f) => f.key));
  const extra = profile.entries.filter((e) => !standardKeys.has(e.key));

  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [savedKey, setSavedKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newLabel, setNewLabel] = useState("");
  const [newValue, setNewValue] = useState("");

  // Start each field from what is saved; keep unsaved edits when the list refreshes.
  useEffect(() => {
    setDrafts((prev) => {
      const next: Record<string, string> = {};
      for (const f of profile.standard_fields) next[f.key] = prev[f.key] ?? byKey.get(f.key)?.value ?? "";
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile.entries, profile.standard_fields]);

  async function save(key: string, value: string, label?: string) {
    setBusyKey(key);
    setError(null);
    try {
      const saved = await saveProfileEntry(key, value, label);
      const others = profile.entries.filter((e) => e.key !== key);
      onChange(saved ? [...others, saved].sort((a, b) => a.label.localeCompare(b.label)) : others);
      setSavedKey(key);
      setTimeout(() => setSavedKey((k) => (k === key ? null : k)), 1500);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.message) : "Could not save that.");
    } finally {
      setBusyKey(null);
    }
  }

  async function remove(key: string) {
    setBusyKey(key);
    setError(null);
    try {
      await deleteProfileEntry(key);
      onChange(profile.entries.filter((e) => e.key !== key));
      setDrafts((d) => ({ ...d, [key]: "" }));
    } catch {
      setError("Could not remove that.");
    } finally {
      setBusyKey(null);
    }
  }

  async function addCustom(e: React.FormEvent) {
    e.preventDefault();
    const key = normalizeKey(newLabel);
    if (!key || !newValue.trim()) return;
    await save(key, newValue.trim(), newLabel.trim());
    setNewLabel("");
    setNewValue("");
  }

  return (
    <Section
      title="Your details"
      hint="The agent uses these to fill forms for you, and asks only when something is missing. Stored encrypted. It never gets a field you haven't saved, and passwords can't be saved here."
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {profile.standard_fields.map((f) => {
          const saved = byKey.get(f.key)?.value ?? "";
          const draft = drafts[f.key] ?? "";
          const dirty = draft.trim() !== saved;
          return (
            <label key={f.key} className="block text-xs">
              <span className="text-black/60">{f.label}</span>
              <div className="mt-1 flex gap-1.5">
                <input
                  type={f.type === "date" ? "date" : f.type === "tel" ? "tel" : "text"}
                  value={draft}
                  maxLength={500}
                  onChange={(e) => setDrafts((d) => ({ ...d, [f.key]: e.target.value }))}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && dirty) save(f.key, draft.trim(), f.label);
                  }}
                  className="min-w-0 flex-1 rounded-md border border-black/15 px-2.5 py-1.5 text-sm"
                />
                {busyKey === f.key ? (
                  <Loader2 className="my-auto h-4 w-4 animate-spin text-black/40" />
                ) : savedKey === f.key ? (
                  <Check className="my-auto h-4 w-4 text-green-600" />
                ) : dirty ? (
                  <button
                    type="button"
                    onClick={() => save(f.key, draft.trim(), f.label)}
                    className="rounded-md bg-accent px-2.5 text-xs font-medium text-white hover:bg-accent/90"
                  >
                    Save
                  </button>
                ) : null}
              </div>
            </label>
          );
        })}
      </div>

      <div className="mt-5 border-t border-black/10 pt-4">
        <h3 className="text-xs font-semibold text-black/70">Other saved answers</h3>
        <p className="mt-0.5 text-xs text-black/50">
          Things the agent asked you and you chose to remember, or ones you add yourself (e.g. county, Address).
        </p>
        {extra.length > 0 && (
          <ul className="mt-2 divide-y divide-black/5 text-sm">
            {extra.map((e) => (
              <li key={e.key} className="flex items-center gap-3 py-2">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs text-black/50">{e.label}</p>
                  <p className="truncate">{e.value}</p>
                </div>
                <button
                  onClick={() => remove(e.key)}
                  disabled={busyKey === e.key}
                  aria-label={`Remove ${e.label}`}
                  className="rounded-md p-1.5 text-black/40 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                >
                  {busyKey === e.key ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                </button>
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={addCustom} className="mt-3 flex flex-col gap-2 sm:flex-row">
          <input
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            placeholder="Name (e.g. Home county)"
            maxLength={100}
            className="min-w-0 flex-1 rounded-md border border-black/15 px-2.5 py-1.5 text-sm"
          />
          <input
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            placeholder="Value"
            maxLength={500}
            className="min-w-0 flex-1 rounded-md border border-black/15 px-2.5 py-1.5 text-sm"
          />
          <button
            type="submit"
            disabled={!normalizeKey(newLabel) || !newValue.trim()}
            className="flex items-center justify-center gap-1 rounded-md border border-black/15 px-3 py-1.5 text-sm hover:bg-black/5 disabled:opacity-40"
          >
            <Plus className="h-4 w-4" /> Add
          </button>
        </form>
      </div>
      {error && <p className="mt-3 text-xs text-red-600">{error}</p>}
    </Section>
  );
}
