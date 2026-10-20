"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowRight, Link2, ShieldAlert } from "lucide-react";
import { ApiError, createRegistrationJob, getProfile, isAuthenticated } from "@/lib/api";
import { invalidate } from "@/lib/cache";
import { extractDirectTarget, isGoogleForm } from "@/lib/directLink";
import { useCachedData } from "@/lib/useCachedData";
import Button, { buttonClass } from "@/components/ui/Button";
import { InlineMessage, PageSpinner } from "@/components/ui/States";

type Target = { state: "loading" } | { state: "invalid" } | { state: "ok"; url: string; host: string };

/**
 * Landing page for shortcut links (/@direct/https://example.com) and the PWA share target.
 * It reads the address, makes you log in if needed, then asks for one confirmation before
 * creating the task. It never creates a task on page load.
 */
export default function DirectPage() {
  const router = useRouter();
  const params = useParams<{ target?: string[] }>();
  const [target, setTarget] = useState<Target>({ state: "loading" });
  const [authed, setAuthed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsSettings, setNeedsSettings] = useState(false);
  const [ambiguous, setAmbiguous] = useState(false);
  const inFlight = useRef(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      // Come back to exactly this link after logging in.
      const here = window.location.pathname + window.location.search + window.location.hash;
      router.replace(`/login?next=${encodeURIComponent(here)}`);
      return;
    }
    setAuthed(true);
    const url = extractDirectTarget({
      segments: params.target,
      search: window.location.search,
      hash: window.location.hash,
    });
    if (!url) setTarget({ state: "invalid" });
    else setTarget({ state: "ok", url, host: new URL(url).host });
  }, [params.target, router]);

  const { data: profile } = useCachedData(authed ? "profile" : null, getProfile);

  async function start() {
    if (target.state !== "ok" || inFlight.current) return;
    inFlight.current = true;
    setSubmitting(true);
    setError(null);
    setNeedsSettings(false);
    setAmbiguous(false);
    try {
      const job = await createRegistrationJob(target.url);
      invalidate("jobs");
      router.replace(`/jobs/${job.id}`); // replace: Back must not return to this confirmation
    } catch (err) {
      if (err instanceof ApiError && err.status < 500) {
        const body = err.body as { url?: string[] | string; detail?: string } | undefined;
        const urlErr = Array.isArray(body?.url) ? body?.url?.[0] : body?.url;
        const detail = urlErr || body?.detail || (err.status === 429 ? "Too many tasks started recently. Try again shortly." : "Could not start the task.");
        setError(String(detail));
        setNeedsSettings(/Settings/.test(String(detail)));
      } else {
        setAmbiguous(true);
      }
      inFlight.current = false;
      setSubmitting(false);
    }
  }

  if (!authed || target.state === "loading") return <PageSpinner label="Reading the link" />;

  if (target.state === "invalid") {
    return (
      <div className="mx-auto max-w-md space-y-3">
        <InlineMessage tone="danger">
          That link did not contain a website address the agent can use. Use a full address such as https://example.com/signup.
        </InlineMessage>
        <Link href="/new" className={buttonClass("primary")}>Go to Home</Link>
      </div>
    );
  }

  const form = isGoogleForm(target.url);
  return (
    <div className="mx-auto max-w-md space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{form ? "Fill in this form?" : "Create a login for this site?"}</h1>
        <p className="mt-1 text-sm text-muted">
          You opened a shortcut link. Nothing has started yet: check the address, then confirm.
        </p>
      </div>

      <div className="rounded-lg border border-line bg-surface p-4">
        <p className="flex items-center gap-2 text-xs font-medium text-muted">
          <Link2 className="h-3.5 w-3.5" aria-hidden="true" /> Website
        </p>
        <p className="mt-1 break-all font-mono text-base font-semibold">{target.host}</p>
        <p className="mt-1 break-all font-mono text-xs text-muted">{target.url}</p>
        {!form && profile && (
          <p className="mt-3 border-t border-line pt-3 text-xs text-muted">
            Identity: <span className="font-medium text-ink">{profile.account_mode === "permanent" ? "Permanent identity" : "Temporary identity"}</span>.{" "}
            <Link href="/settings" className="text-accent-strong underline">Change in Settings</Link>
          </p>
        )}
      </div>

      <p className="flex items-start gap-2 text-xs text-muted">
        <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        Only continue if you meant to open this. Anyone can send a link like this, and the agent will act on this address under your account.
      </p>

      {error && (
        <InlineMessage tone="danger">
          {error} {needsSettings && <Link href="/settings" className="font-medium underline">Open Settings</Link>}
        </InlineMessage>
      )}
      {ambiguous && (
        <InlineMessage tone="warning">
          We could not confirm whether the task was created. Check <Link href="/dashboard" className="font-medium underline">Activity</Link> before trying again.
        </InlineMessage>
      )}

      <div className="flex gap-3">
        <Button variant="primary" className="flex-1" onClick={start} loading={submitting}>
          {form ? "Fill in form" : "Start task"} {!submitting && <ArrowRight className="h-4 w-4" aria-hidden="true" />}
        </Button>
        <Link href="/new" className={buttonClass("secondary")}>Cancel</Link>
      </div>
    </div>
  );
}
