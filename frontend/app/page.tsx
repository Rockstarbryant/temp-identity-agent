"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createRegistrationJob, isAuthenticated, ApiError } from "@/lib/api";
import { Loader2, ShieldAlert } from "lucide-react";

export default function LandingPage() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

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
        setError(body?.url?.[0] || body?.detail || "Could not create the job.");
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
          Create a temporary account without using your personal email.
        </h1>
        <p className="mx-auto max-w-xl text-black/60">
          Give us a registration URL. Our agent generates a temporary identity, fills
          the form, verifies the email, and hands you the credentials — never
          bypassing CAPTCHAs or security checks.
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
          Create Temporary Account
        </button>
      </form>

      {error && (
        <div className="flex items-center gap-2 rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">
          <ShieldAlert className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      <p className="text-xs text-black/40">
        We never attempt to bypass CAPTCHA, SMS verification, or other security checks.
        If a site requires one, you&apos;ll be asked to complete it yourself.
      </p>
    </div>
  );
}
