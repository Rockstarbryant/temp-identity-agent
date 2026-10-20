"use client";

import { useState } from "react";
import { KeyRound, Plus, Trash2 } from "lucide-react";
import { API_URL, ApiError, ApiKeySummary, createApiKey, revokeApiKey } from "@/lib/api";
import Button from "@/components/ui/Button";
import CopyButton from "@/components/ui/CopyButton";
import Field from "@/components/ui/Field";
import { InlineMessage } from "@/components/ui/States";
import { useConfirm } from "@/components/ui/Feedback";
import { formatDateTime } from "@/lib/format";
import Section from "./Section";

interface Props {
  keys: ApiKeySummary[];
  onChange: (keys: ApiKeySummary[]) => void;
}

function CopyBox({ text, label }: { text: string; label: string }) {
  return (
    <div className="relative">
      <pre className="overflow-x-auto rounded-md border border-line bg-subtle p-3 pr-20 font-mono text-xs">{text}</pre>
      <div className="absolute right-1.5 top-1.5">
        <CopyButton value={text} label={label} withText className="bg-surface" />
      </div>
    </div>
  );
}

export default function McpCard({ keys, onChange }: Props) {
  const confirm = useConfirm();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [fresh, setFresh] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // The only endpoint shown is the one derived from the app's configured API URL.
  const endpoint = `${API_URL}/mcp/`;
  const config = JSON.stringify(
    { mcpServers: { "temp-identity-agent": { url: endpoint, headers: { Authorization: `Bearer ${fresh ?? "YOUR_API_KEY"}` } } } },
    null,
    2,
  );

  const manual = keys.filter((k) => k.kind !== "oauth");
  const oauth = keys.filter((k) => k.kind === "oauth");

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await createApiKey(name.trim() || "MCP client");
      setFresh(created.key);
      setName("");
      onChange([{ id: created.id, name: created.name, prefix: created.prefix, kind: created.kind, created_at: created.created_at, last_used_at: null }, ...keys]);
    } catch (err) {
      const body = err instanceof ApiError ? (err.body as { detail?: string } | undefined) : undefined;
      setError(body?.detail || "Could not create the key.");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(k: ApiKeySummary) {
    const isOauth = k.kind === "oauth";
    const ok = await confirm({
      title: isOauth ? `Disconnect ${k.name}?` : `Revoke the key "${k.name}"?`,
      description: isOauth
        ? "This AI client will lose access immediately. It can ask for access again later."
        : "Any AI client using this key will stop working immediately.",
      confirmLabel: isOauth ? "Disconnect" : "Revoke key",
      destructive: true,
    });
    if (!ok) return;
    setRevoking(k.id);
    setError(null);
    try {
      await revokeApiKey(k.id);
      onChange(keys.filter((x) => x.id !== k.id));
    } catch {
      setError("Could not revoke that. It is still active.");
    } finally {
      setRevoking(null);
    }
  }

  const KeyList = ({ items, oauthList }: { items: ApiKeySummary[]; oauthList?: boolean }) => (
    <ul className="divide-y divide-line rounded-md border border-line text-sm">
      {items.map((k) => (
        <li key={k.id} className="flex items-center gap-3 px-3 py-2.5">
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium">{k.name}</p>
            <p className="text-xs text-muted">
              {oauthList ? "Signed-in connection, renews itself" : <span className="font-mono">{k.prefix}…</span>}
              <span aria-hidden="true"> · </span>
              {k.last_used_at ? `last used ${formatDateTime(k.last_used_at)}` : "never used"}
            </p>
          </div>
          <Button
            size="sm" variant="danger-ghost" loading={revoking === k.id} disabled={revoking !== null}
            onClick={() => void revoke(k)} aria-label={`${oauthList ? "Disconnect" : "Revoke"} ${k.name}`}
          >
            {revoking !== k.id && <Trash2 className="h-4 w-4" aria-hidden="true" />}
            <span className="hidden sm:inline">{oauthList ? "Disconnect" : "Revoke"}</span>
          </Button>
        </li>
      ))}
    </ul>
  );

  return (
    <Section
      title="MCP integrations"
      hint="Let Claude, Cursor or any MCP client ask this agent to register on a site and bring back information from it. The agent only proceeds on sites that support email and password sign-in. Account passwords are never sent to AI clients."
    >
      <div className="space-y-5">
        <div>
          <p className="mb-1 text-xs font-medium">Server URL</p>
          <CopyBox text={endpoint} label="server URL" />
          <p className="mt-2 text-xs text-muted">
            <span className="font-medium text-ink">claude.ai:</span> Settings, Connectors, Add custom connector. Paste this URL and approve the sign-in request when asked.
            No key is needed. <span className="font-medium text-ink">Claude Code, Cursor and other clients:</span> create a key below.
          </p>
        </div>

        {fresh && (
          <div className="space-y-2 rounded-md border border-warning-line bg-warning-soft p-3">
            <p className="flex items-center gap-1.5 text-xs font-medium text-warning">
              <KeyRound className="h-3.5 w-3.5" aria-hidden="true" /> Copy your key now. It is shown only once.
            </p>
            <CopyBox text={fresh} label="API key" />
            <p className="text-xs text-muted">Config for clients that take a JSON file:</p>
            <CopyBox text={config} label="client config" />
            <Button size="sm" onClick={() => setFresh(null)}>I have saved it</Button>
          </div>
        )}

        <form onSubmit={create} className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <Field className="min-w-0 flex-1" label="New API key name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Claude Desktop" maxLength={80} />
          <Button type="submit" variant="primary" loading={busy}>
            {!busy && <Plus className="h-4 w-4" aria-hidden="true" />} Create key
          </Button>
        </form>

        {manual.length > 0 && (
          <div>
            <h3 className="mb-1.5 text-xs font-semibold">API keys</h3>
            <KeyList items={manual} />
          </div>
        )}
        {oauth.length > 0 && (
          <div>
            <h3 className="mb-1.5 text-xs font-semibold">Connected AI clients</h3>
            <KeyList items={oauth} oauthList />
          </div>
        )}
        {keys.length === 0 && <p className="text-xs text-muted">No keys or connected clients yet.</p>}

        <p className="text-xs text-muted">Tools offered to clients: register_on_site, get_job, list_jobs, answer_question, cancel_job.</p>
        {error && <InlineMessage tone="danger">{error}</InlineMessage>}
      </div>
    </Section>
  );
}
