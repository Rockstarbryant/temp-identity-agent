"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, Loader2, ShieldAlert, ShieldCheck } from "lucide-react";
import { ApiError, OAuthParams, approveOAuth, getOAuthInfo, isAuthenticated } from "@/lib/api";

const KEYS = ["client_id", "redirect_uri", "state", "code_challenge", "code_challenge_method", "scope", "resource", "response_type"];

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
      <div className="mx-auto max-w-sm space-y-3 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        <p className="flex items-center gap-2 font-medium"><ShieldAlert className="h-4 w-4" /> Can&apos;t continue</p>
        <p>{error}</p>
      </div>
    );
  }
  if (!info) {
    return <div className="flex justify-center py-16 text-black/40"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  }

  return (
    <div className="mx-auto max-w-sm space-y-5">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-5 w-5 text-accent" />
        <h1 className="text-lg font-semibold">Allow {info.client_name}?</h1>
      </div>
      <p className="text-sm text-black/70">
        <span className="font-medium">{info.client_name}</span>
        {info.redirect_host && <span className="text-black/50"> ({info.redirect_host})</span>} wants to use your Temp Identity
        Agent account.
      </p>
      <ul className="space-y-2 rounded-md border border-black/10 bg-white p-4 text-sm">
        {[
          "Start jobs that register on websites with an email and password",
          "See the status and results of those jobs",
          "Answer questions the agent asks while a job runs",
        ].map((t) => (
          <li key={t} className="flex items-start gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-600" /> {t}</li>
        ))}
      </ul>
      <p className="text-xs text-black/50">
        It can&apos;t see your saved passwords. You can disconnect it any time from Settings, under the MCP section.
      </p>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>}
      <div className="flex gap-3">
        <button
          onClick={() => decide(true)} disabled={busy !== null}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-60"
        >
          {busy === "allow" && <Loader2 className="h-4 w-4 animate-spin" />} Allow
        </button>
        <button
          onClick={() => decide(false)} disabled={busy !== null}
          className="flex-1 rounded-md border border-black/15 px-4 py-2 text-sm hover:bg-black/5 disabled:opacity-60"
        >
          Deny
        </button>
      </div>
    </div>
  );
}

export default function OAuthAuthorizePage() {
  return (
    <Suspense fallback={<div className="flex justify-center py-16 text-black/40"><Loader2 className="h-6 w-6 animate-spin" /></div>}>
      <Authorize />
    </Suspense>
  );
}
