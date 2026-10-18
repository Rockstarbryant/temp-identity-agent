"use client";

import { useState } from "react";
import { Check, Copy, KeyRound, Loader2, Plus, Trash2 } from "lucide-react";
import { API_URL, ApiError, ApiKeySummary, createApiKey, revokeApiKey } from "@/lib/api";
import Section from "./Section";

interface Props {
  keys: ApiKeySummary[];
  onChange: (keys: ApiKeySummary[]) => void;
}

function CopyBox({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="relative">
      <pre className="overflow-x-auto rounded-md bg-black/[0.04] p-3 pr-16 text-xs">{text}</pre>
      <button
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          } catch {
            /* clipboard unavailable */
          }
        }}
        aria-label={`Copy ${label}`}
        className="absolute right-2 top-2 flex items-center gap-1 rounded border border-black/10 bg-white px-2 py-1 text-xs hover:bg-black/5"
      >
        {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />} {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

export default function McpCard({ keys, onChange }: Props) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [fresh, setFresh] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const endpoint = `${API_URL}/mcp/`;
  const config = JSON.stringify(
    { mcpServers: { "temp-identity-agent": { url: endpoint, headers: { Authorization: `Bearer ${fresh ?? "YOUR_API_KEY"}` } } } },
    null,
    2,
  );

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await createApiKey(name.trim() || "MCP client");
      setFresh(created.key);
      setName("");
      onChange([{ id: created.id, name: created.name, prefix: created.prefix, created_at: created.created_at, last_used_at: null }, ...keys]);
    } catch (err) {
      const body = err instanceof ApiError ? (err.body as { detail?: string } | undefined) : undefined;
      setError(body?.detail || "Could not create the key.");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: string) {
    if (!confirm("Revoke this key? Any AI client using it will stop working.")) return;
    setRevoking(id);
    setError(null);
    try {
      await revokeApiKey(id);
      onChange(keys.filter((k) => k.id !== id));
    } catch {
      setError("Could not revoke the key.");
    } finally {
      setRevoking(null);
    }
  }

  return (
    <Section
      title="Let other AI tools use this agent (MCP)"
      hint="Connect Claude, Cursor or any MCP client. It can ask this agent to register on a site and bring back information from it. The agent only proceeds on sites that support email + password sign-in."
    >
      <div className="space-y-4">
        <div>
          <p className="mb-1 text-xs text-black/60">Server URL</p>
          <CopyBox text={endpoint} label="server URL" />
          <p className="mt-2 text-xs text-black/50">
            <span className="font-medium text-black/70">claude.ai:</span> Settings → Connectors → Add custom connector, paste
            this URL and sign in when asked. No key needed. <span className="font-medium text-black/70">Claude Code, Cursor and
            others:</span> create a key below.
          </p>
        </div>

        {fresh && (
          <div className="space-y-2 rounded-md border border-amber-200 bg-amber-50 p-3">
            <p className="flex items-center gap-1.5 text-xs font-medium text-amber-900">
              <KeyRound className="h-3.5 w-3.5" /> Copy your key now. It is shown only once.
            </p>
            <CopyBox text={fresh} label="API key" />
            <p className="text-xs text-amber-900/80">Config for clients that take a JSON file:</p>
            <CopyBox text={config} label="client config" />
            <button onClick={() => setFresh(null)} className="text-xs text-amber-900 underline">
              I&apos;ve saved it
            </button>
          </div>
        )}

        <form onSubmit={create} className="flex gap-2">
          <input
            value={name} onChange={(e) => setName(e.target.value)} placeholder="Key name (e.g. Claude Desktop)" maxLength={80}
            className="min-w-0 flex-1 rounded-md border border-black/15 px-3 py-2 text-sm"
          />
          <button
            type="submit" disabled={busy}
            className="flex items-center gap-1.5 rounded-md bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-60"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} New key
          </button>
        </form>

        {keys.length > 0 && (
          <ul className="divide-y divide-black/5 text-sm">
            {keys.map((k) => (
              <li key={k.id} className="flex items-center gap-3 py-2">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{k.name}</p>
                  <p className="text-xs text-black/50">
                    {k.kind === "oauth" ? "Signed-in connection (renews itself)" : `${k.prefix}…`} · {k.last_used_at ? `last used ${new Date(k.last_used_at).toLocaleString()}` : "never used"}
                  </p>
                </div>
                <button
                  onClick={() => revoke(k.id)} disabled={revoking === k.id} aria-label={`Revoke ${k.name}`}
                  className="rounded-md p-1.5 text-black/40 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                >
                  {revoking === k.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-black/40">
          Tools: register_on_site, get_job, list_jobs, answer_question, cancel_job. Account passwords are never sent to
          AI clients; they stay in your vault.
        </p>
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    </Section>
  );
}
