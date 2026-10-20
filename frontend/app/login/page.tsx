"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { ApiError, login } from "@/lib/api";
import { safeNextPath } from "@/lib/useRequireAuth";
import Button from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import { InlineMessage, PageSpinner } from "@/components/ui/States";

function LoginForm() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const searchParams = useSearchParams();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      router.push(safeNextPath(searchParams.get("next")));
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 429 ? "Too many attempts. Wait a minute and try again." : "Invalid username or password."
          : "Could not reach the server. Check your connection and try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="text-xl font-semibold tracking-tight">Log in</h1>
      <p className="mt-1 text-sm text-muted">Welcome back to Temp Identity Agent.</p>
      <form onSubmit={handleSubmit} className="mt-6 space-y-4 rounded-lg border border-line bg-surface p-5">
        <Field label="Username" required value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoCapitalize="none" />
        <Field
          label="Password" required type={show ? "text" : "password"} value={password}
          onChange={(e) => setPassword(e.target.value)} autoComplete="current-password"
          trailing={
            <button
              type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"} aria-pressed={show}
              className="rounded p-1.5 text-muted hover:bg-subtle hover:text-ink"
            >
              {show ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
            </button>
          }
        />
        {error && <InlineMessage tone="danger">{error}</InlineMessage>}
        <Button type="submit" variant="primary" loading={loading} className="w-full">Log in</Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted">
        No account? <Link href="/register" className="text-accent-strong underline">Sign up</Link>
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <LoginForm />
    </Suspense>
  );
}
