"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createRegistrationJob, isAuthenticated, ApiError } from "@/lib/api";
import Link from "next/link";
import { FileText, Loader2, ShieldAlert, Terminal, Cpu } from "lucide-react";

function isGoogleForm(raw: string) {
  try {
    const u = new URL(raw);
    return (u.hostname === "docs.google.com" && u.pathname.startsWith("/forms")) || u.hostname === "forms.gle";
  } catch {
    return false;
  }
}

export default function LandingPage() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsSettings, setNeedsSettings] = useState(false);
  const router = useRouter();
  const form = isGoogleForm(url);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!isAuthenticated()) {
      router.push(`/login?next=/`);
      return;
    }

    setLoading(true);
    try {
      const job = await createRegistrationJob(url);
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        const body = err.body as { url?: string[]; detail?: string } | undefined;
        const detail = body?.url?.[0] || body?.detail || "Could not create the job.";
        setError(detail);
        setNeedsSettings(/Settings/.test(detail));
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center justify-center px-4 py-20 text-center">
      {/* Agent Status Badge */}
      <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-black/10 bg-black/5 px-3 py-1 font-mono text-xs text-black/70">
        <span className="h-2 w-2 rounded-full bg-emerald-600 animate-pulse" />
        <span>AGENT_CORE // READY</span>
      </div>

      {/* Hero Header */}
      <div className="space-y-4">
        <h1 className="text-4xl font-semibold tracking-tight text-black sm:text-5xl">
          Let an agent sign you up, or fill in a form for you.
        </h1>
        <p className="mx-auto max-w-xl text-sm leading-relaxed text-black/60">
          Paste a registration page or a Google Form. For accounts, the agent uses a throwaway identity or your own
          email (see Settings), fills the form, verifies the email, and hands you the credentials. It asks you
          for anything it doesn&apos;t know and never bypasses CAPTCHAs or security checks.
        </p>
      </div>

      {/* Terminal Command Input Box */}
      <div className="mt-8 w-full max-w-xl rounded-lg border border-black/15 bg-white p-2">
        <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row">
          <div className="flex flex-1 items-center gap-2 rounded-md bg-black/5 px-3 py-2.5">
            <Terminal className="h-4 w-4 shrink-0 text-black/40" />
            <input
              type="url"
              required
              placeholder="https://example.com/register"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full bg-transparent text-sm text-black outline-none placeholder:text-black/30"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="flex items-center justify-center gap-2 rounded-md bg-black px-6 py-2.5 text-sm font-medium text-white transition-opacity hover:bg-black/80 disabled:opacity-50"
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            <span>{form ? "Execute Form Fill" : "Deploy Agent"}</span>
          </button>
        </form>
      </div>

      {/* Dynamic Feedback Containers */}
      <div className="mt-4 flex w-full max-w-xl flex-col gap-3 text-left">
        {form && (
          <div className="flex items-start gap-3 rounded-lg border border-black/15 bg-black/[0.02] p-4 text-sm text-black/80">
            <Cpu className="mt-0.5 h-4 w-4 shrink-0 text-black/60" />
            <div>
              <span className="font-medium text-black">Google Form Detected.</span> The agent reads the form, uses your saved details, asks you about anything it can&apos;t answer, submits it, and shows you exactly what it sent.
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-900">
            <div className="flex items-center gap-2.5">
              <ShieldAlert className="h-4 w-4 shrink-0 text-red-600" />
              <span>{error}</span>
            </div>
            {needsSettings && (
              <Link href="/settings" className="shrink-0 font-medium underline hover:text-red-950">
                Open settings
              </Link>
            )}
          </div>
        )}
      </div>

      {/* Technical Footer Notice */}
      <div className="mt-10 max-w-lg border-t border-black/10 pt-6">
        <p className="font-mono text-xs text-black/40">
          SECURITY_NOTICE: We never attempt to bypass CAPTCHA, SMS verification, or other security checks. If a site requires one, you&apos;ll be asked to complete it yourself.
        </p>
      </div>
    </div>
  );
}
