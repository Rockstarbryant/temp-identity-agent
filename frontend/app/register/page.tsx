"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { ApiError, login, register } from "@/lib/api";
import Button from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import { InlineMessage } from "@/components/ui/States";

type FieldErrors = Partial<Record<"username" | "email" | "password", string>>;

export default function RegisterPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setError(null);
    setFieldErrors({});
    if (password.length < 10) {
      setFieldErrors({ password: "Use at least 10 characters." });
      return;
    }
    setLoading(true);
    try {
      await register(username, password, email);
      await login(username, password);
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError && err.body && typeof err.body === "object") {
        const body = err.body as Record<string, unknown>;
        const first = (k: string) => {
          const v = body[k];
          return Array.isArray(v) ? String(v[0]) : typeof v === "string" ? v : undefined;
        };
        const fe: FieldErrors = { username: first("username"), email: first("email"), password: first("password") };
        if (fe.username || fe.email || fe.password) setFieldErrors(fe);
        else setError(first("detail") || "Could not create the account.");
      } else {
        setError("Could not reach the server. Check your connection and try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="text-xl font-semibold tracking-tight">Create an account</h1>
      <p className="mt-1 text-sm text-muted">Your email is optional and is only used for your own login account.</p>
      <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4 rounded-lg border border-line bg-surface p-5">
        <Field label="Username" required value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoCapitalize="none" error={fieldErrors.username} />
        <Field label="Email (optional)" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" error={fieldErrors.email} />
        <Field
          label="Password" required type={show ? "text" : "password"} value={password}
          onChange={(e) => setPassword(e.target.value)} autoComplete="new-password"
          hint="At least 10 characters." error={fieldErrors.password}
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
        <Button type="submit" variant="primary" loading={loading} className="w-full">Sign up</Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted">
        Already have an account? <Link href="/login" className="text-accent-strong underline">Log in</Link>
      </p>
    </div>
  );
}
