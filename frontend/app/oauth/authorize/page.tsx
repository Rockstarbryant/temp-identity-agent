"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, ShieldAlert, ShieldCheck, XCircle } from "lucide-react";
import { ApiError, OAuthParams, approveOAuth, getOAuthInfo, isAuthenticated } from "@/lib/api";
import Button from "@/components/ui/Button";
import { InlineMessage, PageSpinner } from "@/components/ui/States";

const KEYS = ["client_id", "redirect_uri", "state", "code_challenge", "code_challenge_method", "scope", "resource", "response_type"];

const CAN = [
  "Start tasks that register on websites with an email and password",
  "See the status and results of those tasks",
  "Answer questions the agent asks while a task runs",
];
const CANNOT = [
  "See your saved account passwords",
  "Read your mailboxes or your saved personal details",
];

function Authorize() {
  const router = useRouter();
  const search = useSearchParams();
  const params = useMemo<OAuthParams>(() => {
    const p: OAuthParams = {};
    for (const k of KEYS) {
      const v = search.get(k);
      if (v) p[k] = v;
    }
    return p;
  }, [search]);

  const [info, setInfo] = useState<{ client_name: string; redirect_host: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"allow" | "deny" | null>(null);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace(`/login?next=${encodeURIComponent(`/oauth/authorize?${search.toString()}`)}`);
      return;
    }
    getOAuthInfo(params)
      .then(setInfo)
      .catch((err) => {
        const body = err instanceof ApiError ? (err.body as { detail?: string } | undefined) : undefined;
        setError(body?.detail || "This sign-in request is not valid.");
      });
  }, [params, router, search]);

  async function decide(allow: boolean) {
    if (busy) return;
    setBusy(allow ? "allow" : "deny");
    setError(null);
    try {
      const { redirect_url } = await approveOAuth(params, allow);
      window.location.href = redirect_url;
    } catch (err) {
      const body = err instanceof ApiError ? (err.body as { detail?: string } | undefined) : undefined;
      setError(body?.detail || "Something went wrong. Try again.");
      setBusy(null);
    }
  }

  if (error && !info) {
    return (
      <div role="alert" className="mx-auto max-w-md space-y-2 rounded-lg border border-danger-line bg-danger-soft p-5 text-sm">
        <p className="flex items-center gap-2 font-medium text-danger"><ShieldAlert className="h-4 w-4" aria-hidden="true" /> Cannot continue</p>
        <p className="text-ink">{error}</p>
        <p className="text-xs text-muted">No access was granted. You can close this page.</p>
      </div>
    );
  }
  if (!info) return <PageSpinner label="Checking the request" />;

  return (
    <div className="mx-auto max-w-md space-y-5">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-5 w-5 text-accent" aria-hidden="true" />
        <h1 className="text-lg font-semibold tracking-tight">Allow {info.client_name}?</h1>
      </div>

      <div className="rounded-lg border border-line bg-surface p-4 text-sm">
        <dl className="space-y-2">
          <div className="flex justify-between gap-4"><dt className="text-muted">Application</dt><dd className="break-words text-right font-medium">{info.client_name}</dd></div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Returns you to</dt>
            <dd className="break-all text-right font-mono text-xs">{info.redirect_host ?? "Unknown address"}</dd>
          </div>
        </dl>
        {!info.redirect_host && (
          <div className="mt-3"><InlineMessage tone="warning">The return address could not be verified. Only continue if you started this connection yourself.</InlineMessage></div>
        )}
      </div>

      <p className="text-sm text-muted">
        <span className="font-medium text-ink">{info.client_name}</span> is asking to use your Temp Identity Agent account. Only approve this if you started the connection from that app.
      </p>

      <section aria-labelledby="can" className="rounded-lg border border-line bg-surface p-4">
        <h2 id="can" className="mb-2 text-sm font-semibold">It will be able to</h2>
        <ul className="space-y-2 text-sm">
          {CAN.map((t) => (
            <li key={t} className="flex items-start gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" /> {t}</li>
          ))}
        </ul>
        <h2 className="mb-2 mt-4 text-sm font-semibold">It will not be able to</h2>
        <ul className="space-y-2 text-sm">
          {CANNOT.map((t) => (
            <li key={t} className="flex items-start gap-2"><XCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted" aria-hidden="true" /> {t}</li>
          ))}
        </ul>
      </section>

      <p className="text-xs text-muted">You can disconnect it at any time in Settings, under Developer and MCP.</p>
      {error && <InlineMessage tone="danger">{error}</InlineMessage>}
      <div className="flex gap-3">
        <Button variant="primary" className="flex-1" onClick={() => void decide(true)} loading={busy === "allow"} disabled={busy !== null}>Allow</Button>
        <Button className="flex-1" onClick={() => void decide(false)} loading={busy === "deny"} disabled={busy !== null}>Deny</Button>
      </div>
    </div>
  );
}

export default function OAuthAuthorizePage() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <Authorize />
    </Suspense>
  );
}
