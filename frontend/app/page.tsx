"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Hourglass, Infinity as InfinityIcon, KeyRound, Loader2, Search } from "lucide-react";
import {
  AccountMode, ApiError, createRegistrationJob, getProfile, isAuthenticated, listRegistrationJobs, setAccountMode,
  type ProfileData,
} from "@/lib/api";
import { invalidate } from "@/lib/cache";
import { useCachedData } from "@/lib/useCachedData";
import { timeAgo } from "@/lib/format";
import StateBadge from "@/components/StateBadge";
import Button, { buttonClass } from "@/components/ui/Button";
import { InlineMessage } from "@/components/ui/States";
import { cn } from "@/components/ui/cn";

function isGoogleForm(raw: string) {
  try {
    const u = new URL(raw);
    return (u.hostname === "docs.google.com" && u.pathname.startsWith("/forms")) || u.hostname === "forms.gle";
  } catch {
    return false;
  }
}

/** Accepts "example.com/signup" as well as full URLs. Returns null when it is not a usable http(s) URL. */
function normalizeUrl(raw: string): string | null {
  const text = raw.trim();
  if (!text) return null;
  const withScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(text) ? text : `https://${text}`;
  try {
    const u = new URL(withScheme);
    if (u.protocol !== "https:" && u.protocol !== "http:") return null;
    if (!u.hostname.includes(".") && u.hostname !== "localhost") return null;
    return u.toString();
  } catch {
    return null;
  }
}

const MODES: { mode: AccountMode; title: string; text: string; icon: typeof Hourglass }[] = [
  { mode: "temporary", title: "Temporary identity", text: "Throwaway name and disposable inbox. Nothing links back to you.", icon: Hourglass },
  { mode: "permanent", title: "Permanent identity", text: "Your own email and saved details. The account really belongs to you.", icon: InfinityIcon },
];

export default function HomePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [needsSettings, setNeedsSettings] = useState(false);
  const [ambiguous, setAmbiguous] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [savingMode, setSavingMode] = useState<AccountMode | null>(null);
  const [modeError, setModeError] = useState<string | null>(null);
  const inFlight = useRef(false);

  // Read after mount so server and client markup match.
  const [signedIn, setSignedIn] = useState(false);
  useEffect(() => {
    setSignedIn(isAuthenticated());
  }, []);

  const { data: profile, mutate: mutateProfile } = useCachedData<ProfileData>(signedIn ? "profile" : null, getProfile);
  const { data: jobs } = useCachedData(signedIn ? "jobs" : null, async () => (await listRegistrationJobs()).results);

  const form = isGoogleForm(url.trim());
  const mode = profile?.account_mode;
  const recent = (jobs ?? []).slice(0, 5);

  async function chooseMode(next: AccountMode) {
    if (next === mode || savingMode) return;
    setSavingMode(next);
    setModeError(null);
    try {
      await setAccountMode(next);
      mutateProfile((p) => (p ? { ...p, account_mode: next } : p));
    } catch (err) {
      setModeError(err instanceof ApiError ? err.message : "Could not change the default. Nothing was changed.");
    } finally {
      setSavingMode(null);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (inFlight.current || submitting) return;
    setError(null);
    setNeedsSettings(false);
    setAmbiguous(false);

    if (!isAuthenticated()) {
      router.push("/login?next=/");
      return;
    }
    const normalized = normalizeUrl(url);
    if (!normalized) {
      setError("Enter a valid website address, for example https://example.com/signup.");
      return;
    }
    if (savingMode) {
      setError("Wait for the identity type to finish saving.");
      return;
    }

    inFlight.current = true;
    setSubmitting(true);
    try {
      const job = await createRegistrationJob(normalized);
      invalidate("jobs");
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status < 500) {
        const body = err.body as { url?: string[] | string; detail?: string } | undefined;
        const urlErr = Array.isArray(body?.url) ? body?.url?.[0] : body?.url;
        const detail = urlErr || body?.detail || (err.status === 429 ? "Too many tasks started recently. Try again shortly." : "Could not start the task.");
        setError(String(detail));
        setNeedsSettings(/Settings/.test(String(detail)));
      } else {
        // Network failure, timeout or a 5xx: the server may or may not have created the task.
        setAmbiguous(true);
      }
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">What should the agent do?</h1>
        <p className="mt-1.5 text-sm text-muted">
          Paste a sign-up page or a Google Form. The agent fills it in, handles email verification, and asks you for
          anything it does not know. It never bypasses CAPTCHAs or other security checks.
        </p>
      </div>

      <form onSubmit={handleSubmit} noValidate className="rounded-lg border border-line bg-surface p-3 sm:p-4">
        <label htmlFor="task-url" className="mb-2 block text-xs font-medium">Website address</label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden="true" />
            <input
              id="task-url"
              type="text"
              inputMode="url"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              placeholder="https://example.com/register"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              aria-invalid={error && !needsSettings ? true : undefined}
              aria-describedby="task-url-help"
              className="min-h-11 w-full rounded-md border border-line-strong bg-surface py-2 pl-9 pr-3 font-mono text-sm placeholder:text-muted/80 aria-[invalid=true]:border-danger"
            />
          </div>
          <Button type="submit" variant="primary" loading={submitting} className="min-h-11 sm:px-5">
            {form ? "Fill in form" : "Start task"}
            {!submitting && <ArrowRight className="h-4 w-4" aria-hidden="true" />}
          </Button>
        </div>
        <p id="task-url-help" className="mt-2 text-xs text-muted">
          {form
            ? "Google Form detected. The agent reads the form, uses your saved details, asks about anything it cannot answer, submits it, and shows exactly what it sent."
            : "Registration pages and Google Forms are supported."}
        </p>

        {/* Identity type: the saved default, changeable here. */}
        {!form && (
          <fieldset className="mt-4 border-t border-line pt-4">
            <legend className="text-xs font-medium">Identity for this and later tasks</legend>
            {profile ? (
              <>
                <div className="mt-2 grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Identity type">
                  {MODES.map(({ mode: m, title, text, icon: Icon }) => {
                    const selected = mode === m;
                    return (
                      <button
                        key={m}
                        type="button"
                        role="radio"
                        aria-checked={selected}
                        disabled={savingMode !== null || submitting}
                        onClick={() => chooseMode(m)}
                        className={cn(
                          "rounded-md border p-3 text-left transition-colors disabled:cursor-not-allowed",
                          selected ? "border-accent bg-accent-soft" : "border-line-strong hover:bg-subtle",
                        )}
                      >
                        <span className="flex items-center gap-2 text-sm font-medium">
                          {savingMode === m ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Icon className="h-4 w-4" aria-hidden="true" />}
                          {title}
                          {selected && <span className="ml-auto text-xs font-normal text-accent-strong">Default</span>}
                        </span>
                        <span className="mt-1 block text-xs text-muted">{text}</span>
                      </button>
                    );
                  })}
                </div>
                <p className="mt-2 text-xs text-muted">
                  Choosing one changes your default for all new tasks. You can also change it in{" "}
                  <Link href="/settings" className="text-accent-strong underline">Settings</Link>.
                </p>
              </>
            ) : signedIn ? (
              <p className="mt-2 text-xs text-muted">Loading your default identity type</p>
            ) : (
              <p className="mt-2 text-xs text-muted">Log in to choose between a temporary and a permanent identity.</p>
            )}
            {modeError && <div className="mt-2"><InlineMessage tone="danger">{modeError}</InlineMessage></div>}
          </fieldset>
        )}

        {error && (
          <div className="mt-4">
            <InlineMessage tone="danger">
              {error}{" "}
              {needsSettings && <Link href="/settings" className="font-medium underline">Open Settings</Link>}
            </InlineMessage>
          </div>
        )}
        {ambiguous && (
          <div className="mt-4">
            <InlineMessage tone="warning">
              We could not confirm whether the task was created. Check{" "}
              <Link href="/dashboard" className="font-medium underline">Activity</Link> before trying again, so you do not start it twice.
            </InlineMessage>
          </div>
        )}
      </form>

      <section aria-labelledby="recent-heading" className="mt-8">
        <div className="mb-2 flex items-center justify-between">
          <h2 id="recent-heading" className="text-sm font-semibold">Recent activity</h2>
          {signedIn && <Link href="/dashboard" className="text-xs text-accent-strong hover:underline">View all</Link>}
        </div>
        {!signedIn ? (
          <p className="rounded-lg border border-dashed border-line-strong bg-surface px-4 py-6 text-center text-sm text-muted">
            <Link href="/login" className="text-accent-strong underline">Log in</Link> to see your tasks.
          </p>
        ) : jobs === undefined ? (
          <p role="status" className="py-6 text-center text-sm text-muted">Loading</p>
        ) : recent.length === 0 ? (
          <p className="rounded-lg border border-dashed border-line-strong bg-surface px-4 py-6 text-center text-sm text-muted">
            No tasks yet. Your first one will appear here.
          </p>
        ) : (
          <ul className="divide-y divide-line rounded-lg border border-line bg-surface">
            {recent.map((j) => (
              <li key={j.id}>
                <Link href={`/jobs/${j.id}`} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-subtle">
                  <span className="min-w-0">
                    <span className="block truncate font-mono text-sm">{j.domain}</span>
                    <span className="block text-xs text-muted">{timeAgo(j.created_at)}</span>
                  </span>
                  <StateBadge state={j.state} />
                </Link>
              </li>
            ))}
          </ul>
        )}
        {signedIn && (
          <div className="mt-4">
            <Link href="/accounts" className={buttonClass("secondary", "sm")}>
              <KeyRound className="h-4 w-4" aria-hidden="true" /> Open Identity Vault
            </Link>
          </div>
        )}
      </section>
    </div>
  );
}
