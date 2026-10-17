"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { listAccounts, isAuthenticated } from "@/lib/api";
import { useCachedData } from "@/lib/useCachedData";
import { Loader2, KeyRound } from "lucide-react";

export default function AccountsPage() {
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated()) router.push("/login?next=/accounts");
  }, [router]);

  const { data, loading } = useCachedData("accounts", async () => (await listAccounts()).results);
  const accounts = loading ? null : data ?? [];

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold">My Temporary Accounts</h1>

      {accounts === null ? (
        <div className="flex justify-center py-12 text-black/40"><Loader2 className="h-5 w-5 animate-spin" /></div>
      ) : accounts.length === 0 ? (
        <p className="py-12 text-center text-sm text-black/50">
          No temporary accounts yet. <Link href="/" className="text-accent hover:underline">Create one</Link>.
        </p>
      ) : (
        <ul className="divide-y divide-black/10 rounded-md border border-black/10">
          {accounts.map((acct) => (
            <li key={acct.id}>
              <Link href={`/accounts/${acct.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-black/[0.02]">
                <div className="flex items-center gap-3">
                  <KeyRound className="h-4 w-4 text-black/30" />
                  <div>
                    <p className="font-medium">{acct.domain}</p>
                    <p className="text-xs text-black/40">{acct.email}</p>
                  </div>
                </div>
                <span className="text-xs text-black/40">
                  {acct.permanent ? "Permanent account" : `Expires ${new Date(acct.expires_at).toLocaleDateString()}`}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

