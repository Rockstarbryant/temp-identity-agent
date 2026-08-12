"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { register, login, ApiError } from "@/lib/api";
import { Loader2 } from "lucide-react";

export default function RegisterPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(username, password, email);
      await login(username, password);
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError && err.body && typeof err.body === "object") {
        const firstError = Object.values(err.body as Record<string, string[]>)[0];
        setError(Array.isArray(firstError) ? firstError[0] : "Could not create account.");
      } else {
        setError("Something went wrong.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="mb-6 text-xl font-semibold">Create an account</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <input
          type="text" required placeholder="Username" value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="rounded-md border border-black/15 px-4 py-2.5 text-sm outline-none focus:border-accent"
        />
        <input
          type="email" placeholder="Email (optional)" value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="rounded-md border border-black/15 px-4 py-2.5 text-sm outline-none focus:border-accent"
        />
        <input
          type="password" required placeholder="Password (min. 10 characters)" value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="rounded-md border border-black/15 px-4 py-2.5 text-sm outline-none focus:border-accent"
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit" disabled={loading}
          className="flex items-center justify-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-60"
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          Sign up
        </button>
      </form>
      <p className="mt-4 text-sm text-black/60">
        Already have an account? <Link href="/login" className="text-accent hover:underline">Log in</Link>
      </p>
    </div>
  );
}
