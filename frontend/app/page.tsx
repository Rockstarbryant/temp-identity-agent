"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createRegistrationJob, isAuthenticated, ApiError } from "@/lib/api";
import Link from "next/link";
import { FileText, Loader2, ShieldAlert } from "lucide-react";

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
    <div className="flex flex-col items-center gap-8 py-12 text-center">
      <div className="space-y-3">
        <h1 className="text-3xl font-semibold tracking-tight">
          Let an agent sign you up, or fill in a form for you.
        </h1>
        <p className="mx-auto max-w-xl text-black/60">
          Paste a registration page or a Google Form. For accounts, the agent uses a throwaway identity or your own
          email (see Settings), fills the form, verifies the email, and hands you the credentials. It asks you
          for anything it doesn&apos;t know and never bypasses CAPTCHAs or security checks.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex w-full max-w-lg flex-col gap-3 sm:flex-row">
        <input
          type="url"
          required
          placeholder="https://example.com/register"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="flex-1 rounded-md border border-black/15 px-4 py-2.5 text-sm outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={loading}
          className="flex items-center justify-center gap-2 rounded-md bg-accent px-5 py-2.5 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-60"
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          {form ? "Fill in this form" : "Create account"}
        </button>
      </form>

      {form && (
        <p className="flex max-w-lg items-start gap-2 rounded-md bg-blue-50 px-4 py-2 text-left text-sm text-blue-800">
          <FileText className="mt-0.5 h-4 w-4 shrink-0" />
          Google Form detected. The agent reads the form, uses your saved details, asks you about anything it can&apos;t
          answer, submits it, and shows you exactly what it sent.
        </p>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">
          <ShieldAlert className="h-4 w-4 shrink-0" />
          <span>{error}</span>
          {needsSettings && <Link href="/settings" className="shrink-0 font-medium underline">Open settings</Link>}
        </div>
      )}

      <p className="text-xs text-black/40">
        We never attempt to bypass CAPTCHA, SMS verification, or other security checks.
        If a site requires one, you&apos;ll be asked to complete it yourself.
      </p>
    </div>
  );
}
