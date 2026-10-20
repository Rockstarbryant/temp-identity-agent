"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, Plus, Trash2 } from "lucide-react";
import { ApiError, ProfileData, ProfileEntry, deleteProfileEntry, saveProfileEntry } from "@/lib/api";
import Button from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import { InlineMessage } from "@/components/ui/States";
import { useConfirm } from "@/components/ui/Feedback";
import Section from "./Section";

interface Props {
  profile: ProfileData;
  onChange: (entries: ProfileEntry[]) => void;
}

function normalizeKey(raw: string) {
  return raw.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 60);
}

export default function DetailsCard({ profile, onChange }: Props) {
  const confirm = useConfirm();
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
      setTimeout(() => setSavedKey((k) => (k === key ? null : k)), 1800);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.message) : "Could not save that.");
    } finally {
      setBusyKey(null);
    }
  }

  async function remove(key: string, label: string) {
    const ok = await confirm({
      title: `Delete saved detail "${label}"?`,
      description: "The agent will ask you for it again the next time a form needs it.",
      confirmLabel: "Delete",
      destructive: true,
    });
    if (!ok) return;
    setBusyKey(key);
    setError(null);
    try {
      await deleteProfileEntry(key);
      onChange(profile.entries.filter((e) => e.key !== key));
      setDrafts((d) => ({ ...d, [key]: "" }));
    } catch {
      setError("Could not delete that. It is still saved.");
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
      title="Saved personal details"
      hint="The agent may reuse these to fill in forms for you, and asks only when something is missing. They are stored encrypted. Passwords and similar secrets cannot be saved here."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {profile.standard_fields.map((f) => {
          const saved = byKey.get(f.key)?.value ?? "";
          const draft = drafts[f.key] ?? "";
          const dirty = draft.trim() !== saved;
          return (
            <div key={f.key}>
              <Field
                label={f.label}
                type={f.type === "date" ? "date" : f.type === "tel" ? "tel" : "text"}
                value={draft}
                maxLength={500}
                onChange={(e) => setDrafts((d) => ({ ...d, [f.key]: e.target.value }))}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && dirty) {
                    e.preventDefault();
                    void save(f.key, draft.trim(), f.label);
                  }
                }}
              />
              <div className="mt-1.5 flex min-h-8 items-center gap-2">
                {busyKey === f.key ? (
                  <Loader2 className="h-4 w-4 animate-spin text-muted" aria-label="Saving" />
                ) : savedKey === f.key ? (
                  <span role="status" className="inline-flex items-center gap-1 text-xs text-success"><Check className="h-4 w-4" aria-hidden="true" /> Saved</span>
                ) : (
                  <>
                    {dirty && (
                      <Button size="sm" variant="primary" onClick={() => void save(f.key, draft.trim(), f.label)}>
                        {draft.trim() ? "Save" : "Clear"}
                      </Button>
                    )}
                    {!dirty && saved && (
                      <Button size="sm" variant="danger-ghost" onClick={() => void remove(f.key, f.label)}>
                        <Trash2 className="h-3.5 w-3.5" aria-hidden="true" /> Delete
                      </Button>
                    )}
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-6 border-t border-line pt-4">
        <h3 className="text-sm font-semibold">Other saved answers</h3>
        <p className="mt-0.5 text-xs text-muted">
          Things the agent asked you and you chose to remember, or ones you add yourself (for example, Home county).
        </p>
        {extra.length > 0 && (
          <ul className="mt-3 divide-y divide-line rounded-md border border-line text-sm">
            {extra.map((e) => (
              <li key={e.key} className="flex items-center gap-3 px-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs text-muted">
                    {e.label} <span aria-hidden="true">·</span> {e.source === "answer" ? "Remembered from an answer" : "Added in Settings"}
                  </p>
                  <p className="truncate">{e.value}</p>
                </div>
                <Button
                  size="sm" variant="danger-ghost" disabled={busyKey === e.key}
                  onClick={() => void remove(e.key, e.label)} aria-label={`Delete ${e.label}`}
                >
                  {busyKey === e.key ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Trash2 className="h-4 w-4" aria-hidden="true" />}
                </Button>
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={addCustom} className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <Field label="Name" value={newLabel} onChange={(e) => setNewLabel(e.target.value)} placeholder="Home county" maxLength={100} />
          <Field label="Value" value={newValue} onChange={(e) => setNewValue(e.target.value)} maxLength={500} />
          <Button type="submit" disabled={!normalizeKey(newLabel) || !newValue.trim()}>
            <Plus className="h-4 w-4" aria-hidden="true" /> Add
          </Button>
        </form>
      </div>
      {error && <div className="mt-3"><InlineMessage tone="danger">{error}</InlineMessage></div>}
    </Section>
  );
}
